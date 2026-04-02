# ============================================================
# ORIVIA OMS
# 檔案：operations/logic/logic_purchase_orders.py
# 說明：叫貨單管理頁 — 邏輯層
# 功能：載入 purchase_orders 列表、確認單張 PO 狀態
# ============================================================

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from shared.services.data_backend import bust_cache, read_table, update_row_by_match


# ----------------------------------------------------------
# 內部工具
# ----------------------------------------------------------

def _now_str() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ----------------------------------------------------------
# 公開函式
# ----------------------------------------------------------

def load_po_list(
    store_id: str,
    status_filter: str,
    filter_date: date,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    """
    讀取符合條件的 purchase_orders 及其 purchase_order_lines。

    回傳：
      po_df      — 篩選後的 purchase_orders DataFrame
      pol_df     — 對應的 purchase_order_lines DataFrame（已依 po_id 預先過濾）
      vendor_map — {vendor_id: vendor_name}
    """
    po_df = read_table("purchase_orders")
    if po_df.empty:
        return pd.DataFrame(), pd.DataFrame(), {}

    # 依 store_id 過濾
    if store_id and "store_id" in po_df.columns:
        po_df = po_df[po_df["store_id"].astype(str).str.strip() == store_id]

    # 依 po_date 過濾（單日，字串前綴比對以相容 ISO timestamp）
    if "po_date" in po_df.columns:
        date_str = str(filter_date)
        po_df = po_df[
            po_df["po_date"].astype(str).str.strip().str.startswith(date_str)
        ]

    # 依 status 過濾
    if status_filter and status_filter != "全部" and "status" in po_df.columns:
        po_df = po_df[po_df["status"].astype(str).str.strip() == status_filter]

    if po_df.empty:
        return pd.DataFrame(), pd.DataFrame(), {}

    # 依本批 po_ids 過濾 purchase_order_lines
    po_ids = set(po_df["po_id"].astype(str).str.strip().tolist())
    pol_df = read_table("purchase_order_lines")
    if not pol_df.empty and "po_id" in pol_df.columns:
        pol_df = pol_df[pol_df["po_id"].astype(str).str.strip().isin(po_ids)]
    else:
        pol_df = pd.DataFrame()

    # 建立廠商名稱對照表
    vendor_map: dict[str, str] = {}
    vendors_df = read_table("vendors")
    if not vendors_df.empty and "vendor_id" in vendors_df.columns:
        name_col = (
            "vendor_name" if "vendor_name" in vendors_df.columns else None
        )
        if name_col:
            for _, vrow in vendors_df.iterrows():
                vid = str(vrow.get("vendor_id", "")).strip()
                vname = str(vrow.get(name_col, "")).strip()
                if vid:
                    vendor_map[vid] = vname or vid

    return (
        po_df.reset_index(drop=True),
        pol_df.reset_index(drop=True),
        vendor_map,
    )


def confirm_purchase_order(po_id: str, actor: str) -> dict:
    """
    將指定 PO 的 status 由 draft 改為 confirmed。
    回傳 {"ok": bool, "error": str}
    """
    try:
        now = _now_str()
        update_row_by_match(
            "purchase_orders",
            "po_id",
            po_id,
            {
                "status": "confirmed",
                "updated_by": actor,
                "updated_at": now,
            },
        )
        bust_cache("purchase_orders")
        return {"ok": True, "error": ""}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
