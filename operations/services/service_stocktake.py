# ============================================================
# ORIVIA OMS
# 檔案：operations/services/service_stocktake.py
# 說明：盤點查詢服務層
# 功能：載入盤點頁所需的品項清單與單位清單。
# 注意：本檔只負責讀取查詢，不含任何寫入或 UI 邏輯。
# ============================================================

from __future__ import annotations

import pandas as pd

from shared.services.data_backend import read_table
from shared.utils.common_helpers import _get_active_df, _norm, _sort_items_for_operation
from shared.utils.utils_format import unit_label


def get_stocktake_items() -> pd.DataFrame:
    """
    載入所有有效品項，供盤點頁顯示。
    回傳欄位：item_id, name, stock_unit_name, order_unit_name, default_vendor_id
    依 item_id 排序（CLAUDE.md § 6.1）。
    """
    raw_df = read_table("items")
    if raw_df.empty:
        return pd.DataFrame()

    items_df = _get_active_df(raw_df)
    if items_df.empty:
        return pd.DataFrame()

    items_df = _sort_items_for_operation(items_df)

    rows: list[dict] = []
    for _, row in items_df.iterrows():
        item_id = _norm(row.get("item_id", ""))
        if not item_id:
            continue

        name = (
            _norm(row.get("item_name_zh", ""))
            or _norm(row.get("item_name", ""))
            or item_id
        )
        base_unit = _norm(row.get("base_unit", ""))
        raw_stock = _norm(row.get("default_stock_unit", "")) or base_unit
        raw_order = _norm(row.get("default_order_unit", "")) or base_unit

        # unit_label() converts unit_id → display name; falls back to raw value if not found
        stock_unit_name = unit_label(raw_stock) or raw_stock
        order_unit_name = unit_label(raw_order) or raw_order

        rows.append({
            "item_id": item_id,
            "name": name,
            "stock_unit_name": stock_unit_name,
            "order_unit_name": order_unit_name,
            "default_vendor_id": _norm(row.get("default_vendor_id", "")),
            "base_unit": _norm(row.get("base_unit", "")),
        })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).reset_index(drop=True)


def get_stocktake_units(items_df: pd.DataFrame) -> pd.DataFrame:
    """
    建立盤點頁 selectbox 所需的單位清單 DataFrame。
    回傳欄位：name（單位顯示名稱字串）
    保證 items_df 中出現的所有 stock_unit_name / order_unit_name 都在結果中，
    避免 render_item_row() 的 index lookup 出現 IndexError。
    """
    all_names: list[str] = []

    # 主要來源：units 表（unit_name_zh 優先，其次 unit_name）
    try:
        units_raw = read_table("units")
        if not units_raw.empty:
            for _, row in units_raw.iterrows():
                label = _norm(row.get("unit_name_zh", "")) or _norm(row.get("unit_name", ""))
                if label and label not in all_names:
                    all_names.append(label)
    except Exception:
        pass

    # 安全 fallback：將 items_df 中出現但 units 表未收錄的名稱補入
    if not items_df.empty:
        for col in ("stock_unit_name", "order_unit_name"):
            if col in items_df.columns:
                for val in items_df[col].dropna():
                    label = _norm(val)
                    if label and label not in all_names:
                        all_names.append(label)

    # 最終 fallback：確保清單不為空，避免 selectbox 傳入空 options
    if not all_names:
        all_names = ["個"]

    return pd.DataFrame({"name": all_names}).reset_index(drop=True)
