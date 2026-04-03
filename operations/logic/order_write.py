from __future__ import annotations

# =============================================================================
# [v1 STABLE — RPC TRANSACTION WRITE PATH]
# 本模組的 _save_order_entry() 為正式寫入路徑，透過 Supabase RPC transaction
# 原子寫入 stocktakes / stocktake_lines / purchase_orders /
# purchase_order_lines / audit_logs。
#
# 禁止事項：
#   - 不可回退為多 API 寫入（write_stocktake_section / write_purchase_order_section
#     僅保留供其他模組使用，_save_order_entry 不得改回呼叫它們）
#   - 不可在未重新執行 transaction validation 的情況下修改 SQL function
#     （migrations/003–007，特別是 007_fix_rpc_on_conflict_partial.sql）
#   - 任何修改此流程的 PR 必須附上
#     out/YYYYMMDD_rpc_transaction_validation_report.md 驗證結果
# =============================================================================

from operations.logic.order_write_rpc import build_order_write_rpc_payload
from shared.services.service_order_rpc import rpc_save_order_transaction
from shared.services.data_backend import bust_cache


def _save_order_entry(
    submit_rows,
    vendor_items,
    conversions_df,
    store_id,
    vendor_id,
    record_date,
    delivery_date,
    existing_stocktake_id: str = "",
    existing_po_id: str = "",
    is_initial_stock: bool = False,
):
    payload = build_order_write_rpc_payload(
        submit_rows=submit_rows,
        vendor_items=vendor_items,
        conversions_df=conversions_df,
        store_id=store_id,
        vendor_id=vendor_id,
        record_date=record_date,
        delivery_date=delivery_date,
        existing_stocktake_id=existing_stocktake_id,
        existing_po_id=existing_po_id,
        is_initial_stock=is_initial_stock,
    )
    rpc_save_order_transaction(payload)
    bust_cache(["stocktakes", "stocktake_lines", "purchase_orders", "purchase_order_lines"])
    return payload["_meta"]["po_id"]
