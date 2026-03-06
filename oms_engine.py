from __future__ import annotations

from collections import deque
from datetime import datetime, date
from typing import Optional, Tuple

import pandas as pd


# ============================================================
# Basic helpers
# ============================================================
def _to_date(value) -> Optional[date]:
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
    if value is None:
        return ""
    return str(value).strip()


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y", "是"}


# ============================================================
# Conversion filtering
# ============================================================
def _filter_active_conversions(
    conversions_df: pd.DataFrame,
    item_id: str,
    as_of_date: Optional[date] = None,
) -> pd.DataFrame:
    if conversions_df is None or conversions_df.empty:
        return pd.DataFrame()

    work = conversions_df.copy()

    for col in ["item_id", "from_unit", "to_unit"]:
        if col in work.columns:
            work[col] = work[col].apply(_normalize_text)

    # 對齊你的 DB：使用 ratio
    if "ratio" in work.columns:
        work["ratio"] = pd.to_numeric(work["ratio"], errors="coerce")
    else:
        raise ValueError("unit_conversions 缺少 ratio 欄位")

    work = work[work["item_id"] == _normalize_text(item_id)]
    work = work[work["ratio"].notna()]
    work = work[work["ratio"] > 0]

    if "is_active" in work.columns:
        work = work[work["is_active"].apply(_to_bool)]

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
# Build graph
# ============================================================
def _build_unit_graph(valid_df: pd.DataFrame) -> dict:
    graph = {}

    for _, row in valid_df.iterrows():
        from_unit = _normalize_text(row["from_unit"])
        to_unit = _normalize_text(row["to_unit"])
        ratio = float(row["ratio"])

        if not from_unit or not to_unit or ratio <= 0:
            continue

        graph.setdefault(from_unit, []).append((to_unit, ratio))
        graph.setdefault(to_unit, []).append((from_unit, 1 / ratio))

    return graph


# ============================================================
# Core converter
# ============================================================
def convert_unit(
    item_id: str,
    qty: float,
    from_unit: str,
    to_unit: str,
    conversions_df: pd.DataFrame,
    as_of_date: Optional[date] = None,
) -> float:
    item_id = _normalize_text(item_id)
    from_unit = _normalize_text(from_unit)
    to_unit = _normalize_text(to_unit)

    if qty is None:
        raise ValueError("qty 不可為空")
    if from_unit == "":
        raise ValueError("from_unit 不可為空")
    if to_unit == "":
        raise ValueError("to_unit 不可為空")

    qty = float(qty)

    if from_unit == to_unit:
        return qty

    valid_df = _filter_active_conversions(
        conversions_df=conversions_df,
        item_id=item_id,
        as_of_date=as_of_date,
    )

    if valid_df.empty:
        raise ValueError(f"找不到品項 {item_id} 的任何有效單位換算規則")

    graph = _build_unit_graph(valid_df)

    if from_unit not in graph:
        raise ValueError(f"品項 {item_id} 沒有單位 {from_unit} 的換算規則")
    if to_unit not in graph:
        raise ValueError(f"品項 {item_id} 沒有單位 {to_unit} 的換算規則")

    queue = deque([(from_unit, 1.0)])
    visited = {from_unit}

    while queue:
        current_unit, current_factor = queue.popleft()

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
# Base unit helpers
# ============================================================
def get_base_unit(items_df: pd.DataFrame, item_id: str) -> str:
    if items_df is None or items_df.empty:
        raise ValueError("items_df 為空，無法取得 base_unit")

    work = items_df.copy()
    work["item_id"] = work["item_id"].apply(_normalize_text)

    row = work.loc[work["item_id"] == _normalize_text(item_id)]
    if row.empty:
        raise ValueError(f"items 找不到 item_id: {item_id}")

    if "base_unit" not in row.columns:
        raise ValueError("items 缺少 base_unit 欄位")

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
