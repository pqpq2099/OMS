from __future__ import annotations

# ============================================================
# ORIVIA OMS
# 檔案：operations/logic/logic_stock_adjustment.py
# 說明：庫存調整功能的資料載入與寫入邏輯
# 功能：
#   - load_vendors_for_store：取得該分店有庫存記錄的廠商清單
#   - load_items_for_adjustment：載入廠商品項及目前庫存數量
#   - save_adjustment：寫入 stock_adjustments 審計記錄
#                      + stocktake（type=manual_adjustment）供現有查詢相容
# 注意：
#   - 庫存調整權限守衛在 page 層（has_permission("operation.stock.adjust")）
#   - 只允許 base_qty > 0 的品項顯示（可調整至 0，但不顯示已為 0 的品項）
# ============================================================

from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st

from shared.services.data_backend import read_table
from shared.services.supabase_client import insert_rows
from shared.services.service_id import (
    allocate_adjustment_id,
    allocate_stocktake_id,
    allocate_stocktake_line_ids,
)
from shared.utils.utils_units import convert_to_base, convert_unit, get_base_unit


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
    """
    取得指定品項在指定分店的最新 base_qty（以盤點記錄為準）。
    回傳 float，找不到時回傳 0.0。
    """
    if stocktakes_df.empty or stocktake_lines_df.empty:
        return 0.0

    stx = stocktakes_df.copy()
    stl = stocktake_lines_df.copy()

    stx["stocktake_id"] = stx["stocktake_id"].astype(str).str.strip()
    stl["stocktake_id"] = stl["stocktake_id"].astype(str).str.strip()
    stl["item_id"] = stl["item_id"].astype(str).str.strip()

    stx = stx[stx["store_id"].astype(str).str.strip() == str(store_id).strip()].copy()
    if stx.empty:
        return 0.0

    merged = stl.merge(stx[["stocktake_id", "stocktake_date"]], on="stocktake_id", how="inner")
    merged = merged[merged["item_id"] == str(item_id).strip()].copy()
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


# ----------------------------------------------------------------
# 對外介面
# ----------------------------------------------------------------

def load_vendors_for_store(store_id: str, as_of_date: date) -> list[dict]:
    """
    取得該分店有庫存盤點記錄的廠商清單，按廠商名稱排序。
    回傳 [{"vendor_id": ..., "vendor_name": ...}]
    """
    stocktakes_df = read_table("stocktakes")
    stocktake_lines_df = read_table("stocktake_lines")
    vendors_df = read_table("vendors")

    if stocktakes_df.empty or stocktake_lines_df.empty or vendors_df.empty:
        return []

    stx = stocktakes_df.copy()
    stl = stocktake_lines_df.copy()

    stx = stx[stx["store_id"].astype(str).str.strip() == _norm(store_id)].copy()
    if stx.empty:
        return []

    stx["__date"] = stx["stocktake_date"].apply(_parse_date)
    stx = stx[stx["__date"].notna() & (stx["__date"] <= as_of_date)].copy()
    if stx.empty:
        return []

    merged = stl.merge(stx[["stocktake_id"]], on="stocktake_id", how="inner")
    if merged.empty:
        return []

    # 取廠商 ID 清單（排除空值）
    vendor_ids = set()
    for vid in merged["vendor_id"].dropna().astype(str).str.strip():
        if vid:
            vendor_ids.add(vid)

    if not vendor_ids:
        return []

    vendors_df["vendor_id"] = vendors_df["vendor_id"].astype(str).str.strip()
    matched = vendors_df[vendors_df["vendor_id"].isin(vendor_ids)].copy()
    matched = matched.sort_values("vendor_name") if "vendor_name" in matched.columns else matched

    result = []
    for _, row in matched.iterrows():
        result.append({
            "vendor_id": _norm(row.get("vendor_id", "")),
            "vendor_name": _norm(row.get("vendor_name", row.get("vendor_id", ""))),
        })
    return result


def load_items_for_adjustment(
    store_id: str,
    vendor_id: str,
    as_of_date: date,
) -> list[dict]:
    """
    載入指定廠商在指定分店有庫存（base_qty > 0）的品項，附帶目前庫存數量。
    回傳 list[dict]，每個元素包含：
        item_id, item_name, vendor_id,
        current_display_qty, display_unit,
        current_base_qty, base_unit
    按 item_id 排序。
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

    stx = stx[stx["store_id"].astype(str).str.strip() == _norm(store_id)].copy()
    if stx.empty:
        return []

    stx["__date"] = stx["stocktake_date"].apply(_parse_date)
    stx = stx[stx["__date"].notna() & (stx["__date"] <= as_of_date)].copy()
    if stx.empty:
        return []

    merged = stl.merge(stx[["stocktake_id", "stocktake_date"]], on="stocktake_id", how="inner")
    merged["vendor_id_str"] = merged["vendor_id"].astype(str).str.strip()
    merged = merged[merged["vendor_id_str"] == _norm(vendor_id)].copy()
    if merged.empty:
        return []

    # 取此廠商下所有曾有過盤點的品項
    item_ids = merged["item_id"].astype(str).str.strip().unique().tolist()

    result = []
    for item_id in sorted(item_ids):
        base_qty = _get_current_stock_base(stocktakes_df, stocktake_lines_df, store_id, item_id, as_of_date)
        if base_qty <= 0:
            continue  # 只顯示有庫存的品項

        # 取品項資訊
        item_rows = items_df[items_df["item_id"].astype(str).str.strip() == item_id]
        if item_rows.empty:
            continue
        item_row = item_rows.iloc[0]
        item_name = _norm(item_row.get("item_name", item_id))
        base_unit_str = _norm(item_row.get("base_unit", ""))
        display_unit_str = _norm(item_row.get("default_stock_unit", base_unit_str)) or base_unit_str

        # 換算 base_qty → display_qty
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

        result.append({
            "item_id": item_id,
            "item_name": item_name,
            "vendor_id": _norm(vendor_id),
            "current_display_qty": current_display_qty,
            "display_unit": display_unit_str,
            "current_base_qty": round(base_qty, 4),
            "base_unit": base_unit_str,
        })

    return result


def save_adjustment(
    store_id: str,
    adjustment_date: date,
    actor: str,
    changed_items: list[dict],
) -> tuple[bool, str]:
    """
    寫入庫存調整記錄。

    changed_items 每個元素：
        item_id, item_name, vendor_id,
        before_display_qty, after_display_qty, display_unit,
        before_base_qty, after_base_qty, base_unit

    雙寫策略：
      1. stock_adjustments（審計記錄，每個品項一筆）
      2. stocktake + stocktake_lines（type=manual_adjustment，供現有 last-stock 查詢相容）

    回傳 (success: bool, message: str)
    """
    if not changed_items:
        return False, "沒有需要調整的品項"

    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_str = adjustment_date.isoformat()

    try:
        # ── 1. 寫 stock_adjustments（每品項一筆）──────────────────
        adj_rows = []
        for item in changed_items:
            before_base = _safe_float(item.get("before_base_qty", 0))
            after_base = _safe_float(item.get("after_base_qty", 0))
            delta_base = round(after_base - before_base, 4)

            before_disp = _safe_float(item.get("before_display_qty", 0))
            after_disp = _safe_float(item.get("after_display_qty", 0))
            delta_disp = round(after_disp - before_disp, 4)

            adj_id = allocate_adjustment_id()
            adj_rows.append({
                "adjustment_id": adj_id,
                "store_id": _norm(store_id),
                "adjustment_date": date_str,
                "item_id": _norm(item.get("item_id", "")),
                "item_name": _norm(item.get("item_name", "")),
                "vendor_id": _norm(item.get("vendor_id", "")) or None,
                "before_base_qty": round(before_base, 4),
                "delta_base_qty": delta_base,
                "after_base_qty": round(after_base, 4),
                "base_unit": _norm(item.get("base_unit", "")),
                "display_unit": _norm(item.get("display_unit", "")),
                "before_display_qty": round(before_disp, 4),
                "delta_display_qty": delta_disp,
                "after_display_qty": round(after_disp, 4),
                "created_by": _norm(actor),
                "created_at": now_ts,
            })

        insert_rows("stock_adjustments", adj_rows)

        # ── 2. 寫 stocktake + stocktake_lines（相容現有 last-stock 查詢）──
        st_id = allocate_stocktake_id()
        stl_ids = allocate_stocktake_line_ids(len(changed_items))

        stocktake_row = {
            "stocktake_id": st_id,
            "store_id": _norm(store_id),
            "stocktake_date": date_str,
            "vendor_id": None,           # 調整可跨廠商，header 不鎖定廠商
            "stocktake_type": "manual_adjustment",
            "status": "confirmed",
            "note": "庫存調整（系統自動）",
            "created_at": now_ts,
            "created_by": _norm(actor),
            "updated_at": now_ts,
            "updated_by": _norm(actor),
        }
        insert_rows("stocktakes", [stocktake_row])

        stl_rows = []
        for idx, item in enumerate(changed_items):
            after_base = _safe_float(item.get("after_base_qty", 0))
            after_disp = _safe_float(item.get("after_display_qty", 0))
            stl_rows.append({
                "stocktake_line_id": stl_ids[idx],
                "stocktake_id": st_id,
                "store_id": _norm(store_id),
                "vendor_id": _norm(item.get("vendor_id", "")) or None,
                "item_id": _norm(item.get("item_id", "")),
                "item_name": _norm(item.get("item_name", "")),
                "stock_qty": round(after_disp, 4),
                "stock_unit_id": _norm(item.get("display_unit", "")),
                "stock_unit": _norm(item.get("display_unit", "")),
                "base_qty": round(after_base, 4),
                "base_unit": _norm(item.get("base_unit", "")),
                "created_at": now_ts,
                "updated_at": now_ts,
            })
        insert_rows("stocktake_lines", stl_rows)

        return True, f"已完成庫存調整，共 {len(changed_items)} 個品項"

    except Exception as e:
        return False, f"寫入失敗：{e}"
