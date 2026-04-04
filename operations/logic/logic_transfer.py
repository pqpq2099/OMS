from __future__ import annotations

# ============================================================
# ORIVIA OMS
# 檔案：operations/logic/logic_transfer.py
# 說明：調貨功能的資料載入與寫入邏輯
# 功能：
#   - load_stores_for_transfer：取得使用者可存取的分店清單
#   - load_items_for_transfer：載入出貨店有庫存的品項（可選廠商過濾）
#   - save_transfer：寫入調貨記錄（stock_transfers / stock_transfer_lines）
#                    + 同步更新兩店 stocktake
# 注意：
#   - 跨店操作須同時驗證 has_store_access 於兩店（在 page 層驗證）
#   - 調貨立即生效，status = 'confirmed'，無 draft 流程
#   - stocktake 寫入 vendor_id = NULL（轉出）和品項 vendor_id（轉入）
# ============================================================

from datetime import date, datetime

import pandas as pd

from shared.services.data_backend import read_table
from shared.services.supabase_client import insert_rows
from shared.services.service_id import (
    allocate_transfer_id,
    allocate_transfer_line_ids,
    allocate_stocktake_id,
    allocate_stocktake_line_ids,
)
from shared.utils.utils_units import convert_unit, get_base_unit, convert_to_base
from shared.utils.permissions import has_store_access


# ----------------------------------------------------------------
# 內部工具
# ----------------------------------------------------------------

def _safe_float(val) -> float:
    try:
        return float(val) if val is not None and str(val).strip() != "" else 0.0
    except (ValueError, TypeError):
        return 0.0


def _norm(val) -> str:
    return str(val).strip() if val is not None else ""


def _parse_date(val) -> date | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _get_current_stock_base(
    stocktakes_df: pd.DataFrame,
    stocktake_lines_df: pd.DataFrame,
    store_id: str,
    item_id: str,
    as_of_date: date,
) -> float:
    """取指定品項在指定分店的最新 base_qty（≤ as_of_date）。"""
    if stocktakes_df.empty or stocktake_lines_df.empty:
        return 0.0

    stx = stocktakes_df.copy()
    stl = stocktake_lines_df.copy()

    stx["stocktake_id"] = stx["stocktake_id"].astype(str).str.strip()
    stl["stocktake_id"] = stl["stocktake_id"].astype(str).str.strip()
    stl["item_id"] = stl["item_id"].astype(str).str.strip()

    stx = stx[stx["store_id"].astype(str).str.strip() == _norm(store_id)].copy()
    if stx.empty:
        return 0.0

    merged = stl.merge(stx[["stocktake_id", "stocktake_date"]], on="stocktake_id", how="inner")
    merged = merged[merged["item_id"] == _norm(item_id)].copy()
    if merged.empty:
        return 0.0

    merged["__date"] = merged["stocktake_date"].apply(_parse_date)
    merged = merged[
        merged["__date"].notna() & (merged["__date"] <= as_of_date)
    ].copy()
    if merged.empty:
        return 0.0

    merged = merged.sort_values("__date", ascending=True)
    latest = merged.iloc[-1].to_dict()
    base_qty = _safe_float(latest.get("base_qty", latest.get("stock_qty", latest.get("qty", 0))))
    return max(0.0, base_qty)


def _get_item_vendor(stocktakes_df, stocktake_lines_df, store_id, item_id, as_of_date) -> str:
    """取得品項在此店最近一次盤點記錄中的廠商 ID。"""
    if stocktakes_df.empty or stocktake_lines_df.empty:
        return ""
    stx = stocktakes_df.copy()
    stl = stocktake_lines_df.copy()
    stx["stocktake_id"] = stx["stocktake_id"].astype(str).str.strip()
    stl["stocktake_id"] = stl["stocktake_id"].astype(str).str.strip()
    stx = stx[stx["store_id"].astype(str).str.strip() == _norm(store_id)].copy()
    if stx.empty:
        return ""
    merged = stl.merge(stx[["stocktake_id", "stocktake_date"]], on="stocktake_id", how="inner")
    merged = merged[merged["item_id"].astype(str).str.strip() == _norm(item_id)].copy()
    if merged.empty:
        return ""
    merged["__date"] = merged["stocktake_date"].apply(_parse_date)
    merged = merged[merged["__date"].notna() & (merged["__date"] <= as_of_date)].copy()
    if merged.empty:
        return ""
    merged = merged.sort_values("__date", ascending=True)
    return _norm(merged.iloc[-1].get("vendor_id", ""))


# ----------------------------------------------------------------
# 對外介面
# ----------------------------------------------------------------

def load_stores_for_transfer() -> list[dict]:
    """
    取得使用者可存取的分店清單，供選擇出貨店 / 收貨店。
    回傳 [{"store_id": ..., "store_name": ...}]，按 store_name 排序。
    """
    stores_df = read_table("stores")
    if stores_df.empty:
        return []

    result = []
    for _, row in stores_df.iterrows():
        sid = _norm(row.get("store_id", ""))
        if not sid:
            continue
        if not has_store_access(sid):
            continue
        result.append({
            "store_id": sid,
            "store_name": _norm(row.get("store_name", sid)),
        })

    result.sort(key=lambda x: x["store_name"])
    return result


def load_items_for_transfer(
    from_store_id: str,
    as_of_date: date,
) -> list[dict]:
    """
    載入出貨店有庫存（base_qty > 0）的品項，附帶廠商資訊。
    回傳 list[dict]，按 item_id 排序，每個元素包含：
        item_id, item_name, vendor_id,
        current_display_qty, display_unit,
        current_base_qty, base_unit,
        transfer_qty（初始為 0）
    """
    stocktakes_df = read_table("stocktakes")
    stocktake_lines_df = read_table("stocktake_lines")
    items_df = read_table("items")
    conversions_df = read_table("unit_conversions")

    if stocktakes_df.empty or stocktake_lines_df.empty or items_df.empty:
        return []

    stx = stocktakes_df.copy()
    stl = stocktake_lines_df.copy()

    stx["stocktake_id"] = stx["stocktake_id"].astype(str).str.strip()
    stl["stocktake_id"] = stl["stocktake_id"].astype(str).str.strip()

    stx = stx[stx["store_id"].astype(str).str.strip() == _norm(from_store_id)].copy()
    if stx.empty:
        return []

    stx["__date"] = stx["stocktake_date"].apply(_parse_date)
    stx = stx[stx["__date"].notna() & (stx["__date"] <= as_of_date)].copy()
    if stx.empty:
        return []

    merged = stl.merge(stx[["stocktake_id", "stocktake_date"]], on="stocktake_id", how="inner")
    if merged.empty:
        return []

    item_ids = merged["item_id"].astype(str).str.strip().unique().tolist()

    result = []
    for item_id in sorted(item_ids):
        base_qty = _get_current_stock_base(stocktakes_df, stocktake_lines_df, from_store_id, item_id, as_of_date)
        if base_qty <= 0:
            continue

        item_rows = items_df[items_df["item_id"].astype(str).str.strip() == item_id]
        if item_rows.empty:
            continue
        item_row = item_rows.iloc[0]
        item_name = _norm(item_row.get("item_name", item_id))
        base_unit_str = _norm(item_row.get("base_unit", ""))
        display_unit_str = _norm(item_row.get("default_stock_unit", base_unit_str)) or base_unit_str

        try:
            if display_unit_str == base_unit_str or not display_unit_str:
                current_display_qty = round(base_qty, 1)
                display_unit_str = base_unit_str
            else:
                current_display_qty = round(
                    convert_unit(
                        item_id=item_id,
                        qty=base_qty,
                        from_unit=base_unit_str,
                        to_unit=display_unit_str,
                        conversions_df=conversions_df,
                        as_of_date=as_of_date,
                    ),
                    1,
                )
        except Exception:
            current_display_qty = round(base_qty, 1)
            display_unit_str = base_unit_str

        vendor_id = _get_item_vendor(stocktakes_df, stocktake_lines_df, from_store_id, item_id, as_of_date)

        result.append({
            "item_id": item_id,
            "item_name": item_name,
            "vendor_id": vendor_id,
            "current_display_qty": current_display_qty,
            "display_unit": display_unit_str,
            "current_base_qty": round(base_qty, 4),
            "base_unit": base_unit_str,
            "transfer_qty": 0.0,
        })

    return result


def save_transfer(
    from_store_id: str,
    to_store_id: str,
    transfer_date: date,
    actor: str,
    items_to_transfer: list[dict],
) -> tuple[bool, str]:
    """
    寫入調貨記錄。

    items_to_transfer 每個元素：
        item_id, item_name, vendor_id,
        transfer_display_qty, display_unit,
        transfer_base_qty, base_unit,
        current_base_qty（出貨店當前庫存，供計算 after）

    雙寫策略：
      1. stock_transfers（header）+ stock_transfer_lines（明細）
      2. stocktake（出貨店：庫存扣減）+ stocktake（收貨店：庫存增加）
         各自用 type='transfer_out' / 'transfer_in'

    回傳 (success: bool, message: str)
    """
    if not items_to_transfer:
        return False, "沒有需要調貨的品項"
    if _norm(from_store_id) == _norm(to_store_id):
        return False, "出貨店與收貨店不可相同"

    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_str = transfer_date.isoformat()

    try:
        # ── 1. stock_transfers header ─────────────────────────────
        transfer_id = allocate_transfer_id()
        transfer_row = {
            "transfer_id": transfer_id,
            "batch_id": transfer_id,   # 本次調貨 batch = transfer_id
            "transfer_date": date_str,
            "from_store_id": _norm(from_store_id),
            "to_store_id": _norm(to_store_id),
            "status": "confirmed",
            "created_by": _norm(actor),
            "created_at": now_ts,
        }
        insert_rows("stock_transfers", [transfer_row])

        # ── 2. stock_transfer_lines ───────────────────────────────
        line_ids = allocate_transfer_line_ids(len(items_to_transfer))
        line_rows = []
        for idx, item in enumerate(items_to_transfer):
            transfer_base = _safe_float(item.get("transfer_base_qty", 0))
            transfer_disp = _safe_float(item.get("transfer_display_qty", 0))
            line_rows.append({
                "transfer_line_id": line_ids[idx],
                "transfer_id": transfer_id,
                "from_store_id": _norm(from_store_id),
                "to_store_id": _norm(to_store_id),
                "vendor_id": _norm(item.get("vendor_id", "")) or None,
                "item_id": _norm(item.get("item_id", "")),
                "item_name": _norm(item.get("item_name", "")),
                "base_qty": round(transfer_base, 4),
                "base_unit": _norm(item.get("base_unit", "")),
                "display_qty": round(transfer_disp, 4),
                "display_unit": _norm(item.get("display_unit", "")),
                "created_at": now_ts,
            })
        insert_rows("stock_transfer_lines", line_rows)

        # ── 3. stocktake 出貨店（扣減）───────────────────────────
        st_out_id = allocate_stocktake_id()
        stl_out_ids = allocate_stocktake_line_ids(len(items_to_transfer))
        out_stocktake = {
            "stocktake_id": st_out_id,
            "store_id": _norm(from_store_id),
            "stocktake_date": date_str,
            "vendor_id": None,
            "stocktake_type": "transfer_out",
            "status": "confirmed",
            "note": f"調貨轉出至 {_norm(to_store_id)}（{transfer_id}）",
            "created_at": now_ts,
            "created_by": _norm(actor),
            "updated_at": now_ts,
            "updated_by": _norm(actor),
        }
        insert_rows("stocktakes", [out_stocktake])

        out_lines = []
        for idx, item in enumerate(items_to_transfer):
            current_base = _safe_float(item.get("current_base_qty", 0))
            transfer_base = _safe_float(item.get("transfer_base_qty", 0))
            after_base = max(0.0, round(current_base - transfer_base, 4))
            display_unit_str = _norm(item.get("display_unit", ""))
            base_unit_str = _norm(item.get("base_unit", ""))
            transfer_disp = _safe_float(item.get("transfer_display_qty", 0))
            current_disp = _safe_float(item.get("current_display_qty", 0))
            after_disp = max(0.0, round(current_disp - transfer_disp, 4))

            out_lines.append({
                "stocktake_line_id": stl_out_ids[idx],
                "stocktake_id": st_out_id,
                "store_id": _norm(from_store_id),
                "vendor_id": _norm(item.get("vendor_id", "")) or None,
                "item_id": _norm(item.get("item_id", "")),
                "item_name": _norm(item.get("item_name", "")),
                "stock_qty": after_disp,
                "stock_unit_id": display_unit_str,
                "stock_unit": display_unit_str,
                "base_qty": after_base,
                "base_unit": base_unit_str,
                "created_at": now_ts,
                "updated_at": now_ts,
            })
        insert_rows("stocktake_lines", out_lines)

        # ── 4. stocktake 收貨店（增加）───────────────────────────
        st_in_id = allocate_stocktake_id()
        stl_in_ids = allocate_stocktake_line_ids(len(items_to_transfer))

        # 取收貨店目前庫存
        stocktakes_df = read_table("stocktakes")
        stocktake_lines_df = read_table("stocktake_lines")

        in_stocktake = {
            "stocktake_id": st_in_id,
            "store_id": _norm(to_store_id),
            "stocktake_date": date_str,
            "vendor_id": None,
            "stocktake_type": "transfer_in",
            "status": "confirmed",
            "note": f"調貨轉入自 {_norm(from_store_id)}（{transfer_id}）",
            "created_at": now_ts,
            "created_by": _norm(actor),
            "updated_at": now_ts,
            "updated_by": _norm(actor),
        }
        insert_rows("stocktakes", [in_stocktake])

        in_lines = []
        for idx, item in enumerate(items_to_transfer):
            item_id = _norm(item.get("item_id", ""))
            transfer_base = _safe_float(item.get("transfer_base_qty", 0))
            transfer_disp = _safe_float(item.get("transfer_display_qty", 0))
            display_unit_str = _norm(item.get("display_unit", ""))
            base_unit_str = _norm(item.get("base_unit", ""))

            # 收貨店現有庫存 + 調入量
            to_current_base = _get_current_stock_base(
                stocktakes_df, stocktake_lines_df, to_store_id, item_id, transfer_date
            )
            after_in_base = round(to_current_base + transfer_base, 4)
            after_in_disp = round(
                _get_to_store_display_qty(to_current_base, transfer_base, transfer_disp, display_unit_str, base_unit_str),
                4,
            )

            in_lines.append({
                "stocktake_line_id": stl_in_ids[idx],
                "stocktake_id": st_in_id,
                "store_id": _norm(to_store_id),
                "vendor_id": _norm(item.get("vendor_id", "")) or None,
                "item_id": item_id,
                "item_name": _norm(item.get("item_name", "")),
                "stock_qty": after_in_disp,
                "stock_unit_id": display_unit_str,
                "stock_unit": display_unit_str,
                "base_qty": after_in_base,
                "base_unit": base_unit_str,
                "created_at": now_ts,
                "updated_at": now_ts,
            })
        insert_rows("stocktake_lines", in_lines)

        return True, f"調貨完成，共 {len(items_to_transfer)} 個品項（{transfer_id}）"

    except Exception as e:
        return False, f"寫入失敗：{e}"


def _get_to_store_display_qty(
    to_current_base: float,
    transfer_base: float,
    transfer_disp: float,
    display_unit: str,
    base_unit: str,
) -> float:
    """
    計算收貨店調入後的 display_qty。
    使用簡化計算：base 換算比例 = transfer_disp / transfer_base（若相等則 1:1）。
    """
    if transfer_base <= 0:
        return 0.0
    if display_unit == base_unit or not display_unit:
        return to_current_base + transfer_base
    ratio = transfer_disp / transfer_base
    return (to_current_base * ratio) + transfer_disp
