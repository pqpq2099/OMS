"""
工具模組：單位換算。
OMS 的核心規則之一就是：所有計算最後都要回到 base unit。
所以庫存、進貨、成本換算相關邏輯，優先看這個檔案。
"""

# ============================================================
# 單位換算工具
# 用途：
# 1. 根據 unit_conversions 做品項級單位換算
# 2. 支援有效期間 / 啟用狀態過濾
# 3. 支援轉成 base unit
# ============================================================

from __future__ import annotations

from collections import deque
from datetime import date, datetime
from typing import Optional, Tuple

import pandas as pd


# ============================================================
# 基礎工具
# ============================================================
def _to_date(value) -> Optional[date]:
    """
    將各種可能的日期值轉成 date。
    可接受：
    - date
    - datetime
    - 字串
    - pandas 可解析的日期格式

    轉不成功時回傳 None
    """
    if value is None:
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return None

    try:
        return pd.to_datetime(text).date()
    except Exception:
        return None


def _normalize_text(value) -> str:
    """
    將文字標準化：
    - None 轉空字串
    - 去除前後空白
    """
    if value is None:
        return ""
    return str(value).strip()


def _to_bool(value) -> bool:
    """
    將常見布林表示法轉為 True / False
    支援：
    true / 1 / yes / y / 是
    """
    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y", "是"}


# ============================================================
# 過濾有效換算規則
# ============================================================
def _filter_active_conversions(
    conversions_df: pd.DataFrame,
    item_id: str,
    as_of_date: Optional[date] = None,
) -> pd.DataFrame:
    """
    從 unit_conversions 中過濾出某個 item_id 可用的換算規則。

    過濾條件：
    1. item_id 相符
    2. ratio 有值且 > 0
    3. 若有 is_active 欄位，則只保留啟用資料
    4. 若提供 as_of_date，則依 effective_date / end_date 過濾有效期間
    """
    if conversions_df is None or conversions_df.empty:
        return pd.DataFrame()

    work = conversions_df.copy()

    # 先把關鍵欄位標準化，避免空白或 None 造成比對失敗
    for col in ["item_id", "from_unit", "to_unit"]:
        if col in work.columns:
            work[col] = work[col].apply(_normalize_text)

    item_id = _normalize_text(item_id)

    # 你的 DB 規則：使用 ratio 作為換算比例
    if "ratio" in work.columns:
        work["ratio"] = pd.to_numeric(work["ratio"], errors="coerce")
    else:
        raise ValueError("unit_conversions 缺少 ratio 欄位")

    # 只保留該品項的換算規則
    work = work[work["item_id"] == item_id]

    # 只保留 ratio 合法資料
    work = work[work["ratio"].notna()]
    work = work[work["ratio"] > 0]

    # 若有 is_active 欄位，則只保留啟用規則
    if "is_active" in work.columns:
        work = work[work["is_active"].apply(_to_bool)]

    # 若指定日期，則只保留該日期當下有效的規則
    if as_of_date is not None:
        if "effective_date" in work.columns:
            work["_effective_date"] = work["effective_date"].apply(_to_date)
            work = work[
                work["_effective_date"].isna() | (work["_effective_date"] <= as_of_date)
            ]

        if "end_date" in work.columns:
            work["_end_date"] = work["end_date"].apply(_to_date)
            work = work[
                work["_end_date"].isna() | (work["_end_date"] >= as_of_date)
            ]

    return work.copy()


# ============================================================
# 建立單位換算圖
# ============================================================
def _build_unit_graph(valid_df: pd.DataFrame) -> dict:
    """
    將換算表建立成圖(graph)結構，支援多段換算。

    例如：
    箱 -> 包 = 8
    包 -> kg = 1

    系統可自動找到：
    箱 -> 包 -> kg
    """
    graph = {}

    for _, row in valid_df.iterrows():
        from_unit = _normalize_text(row["from_unit"])
        to_unit = _normalize_text(row["to_unit"])
        ratio = float(row["ratio"])

        if not from_unit or not to_unit or ratio <= 0:
            continue

        # 正向換算
        graph.setdefault(from_unit, []).append((to_unit, ratio))

        # 反向換算
        graph.setdefault(to_unit, []).append((from_unit, 1 / ratio))

    return graph


# ============================================================
# 核心換算函式
# ============================================================
def convert_unit(
    item_id: str,
    qty: float,
    from_unit: str,
    to_unit: str,
    conversions_df: pd.DataFrame,
    as_of_date: Optional[date] = None,
) -> float:
    """
    將某個品項的數量，從 from_unit 換算成 to_unit。

    範例：
    convert_unit("ING_001", 2, "箱", "包", conversions_df)

    回傳：
    換算後數量（float）
    """
    item_id = _normalize_text(item_id)
    from_unit = _normalize_text(from_unit)
    to_unit = _normalize_text(to_unit)

    # 基本防呆
    if item_id == "":
        raise ValueError("item_id 不可為空")
    if qty is None:
        raise ValueError("qty 不可為空")
    if from_unit == "":
        raise ValueError("from_unit 不可為空")
    if to_unit == "":
        raise ValueError("to_unit 不可為空")

    qty = float(qty)
    if pd.isna(qty):
        raise ValueError("qty 不可為 NaN")

    # 單位相同就不用換
    if from_unit == to_unit:
        return qty

    # 先篩出該品項可用的換算規則
    valid_df = _filter_active_conversions(
        conversions_df=conversions_df,
        item_id=item_id,
        as_of_date=as_of_date,
    )

    if valid_df.empty:
        raise ValueError(f"找不到品項 {item_id} 的任何有效單位換算規則")

    # 建圖後用 BFS 找到換算路徑
    graph = _build_unit_graph(valid_df)

    if from_unit not in graph:
        raise ValueError(f"品項 {item_id} 沒有單位 {from_unit} 的換算規則")
    if to_unit not in graph:
        raise ValueError(f"品項 {item_id} 沒有單位 {to_unit} 的換算規則")

    queue = deque([(from_unit, 1.0)])
    visited = {from_unit}

    while queue:
        current_unit, current_factor = queue.popleft()

        # 找到目標單位時，回傳換算後數量
        if current_unit == to_unit:
            return qty * current_factor

        for next_unit, ratio in graph.get(current_unit, []):
            if next_unit not in visited:
                visited.add(next_unit)
                queue.append((next_unit, current_factor * ratio))

    raise ValueError(
        f"品項 {item_id} 無法從 {from_unit} 換算到 {to_unit}，請檢查 unit_conversions"
    )


# ============================================================
# Base unit 相關工具
# ============================================================
def get_base_unit(items_df: pd.DataFrame, item_id: str) -> str:
    """
    從 items 表中取得某品項的 base_unit。
    """
    if items_df is None or items_df.empty:
        raise ValueError("items_df 為空，無法取得 base_unit")

    if "item_id" not in items_df.columns:
        raise ValueError("items 缺少 item_id 欄位")
    if "base_unit" not in items_df.columns:
        raise ValueError("items 缺少 base_unit 欄位")

    work = items_df.copy()
    work["item_id"] = work["item_id"].apply(_normalize_text)

    row = work.loc[work["item_id"] == _normalize_text(item_id)]
    if row.empty:
        raise ValueError(f"items 找不到 item_id: {item_id}")

    base_unit = _normalize_text(row.iloc[0]["base_unit"])
    if not base_unit:
        raise ValueError(f"item_id {item_id} 的 base_unit 為空")

    return base_unit


def convert_to_base(
    item_id: str,
    qty: float,
    from_unit: str,
    items_df: pd.DataFrame,
    conversions_df: pd.DataFrame,
    as_of_date: Optional[date] = None,
) -> Tuple[float, str]:
    """
    將某個品項的數量轉成 base unit。

    回傳：
    (base_qty, base_unit)
    """
    base_unit = get_base_unit(items_df, item_id)

    base_qty = convert_unit(
        item_id=item_id,
        qty=qty,
        from_unit=from_unit,
        to_unit=base_unit,
        conversions_df=conversions_df,
        as_of_date=as_of_date,
    )

    return base_qty, base_unit


def can_convert_to_base(
    item_id: str,
    from_unit: str,
    items_df: pd.DataFrame,
    conversions_df: pd.DataFrame,
    as_of_date: Optional[date] = None,
) -> bool:
    """
    檢查某品項是否可以從指定單位成功換算成 base unit。
    可用於 UI 或寫入前驗證。
    """
    try:
        convert_to_base(
            item_id=item_id,
            qty=1,
            from_unit=from_unit,
            items_df=items_df,
            conversions_df=conversions_df,
            as_of_date=as_of_date,
        )
        return True
    except Exception:
        return False
