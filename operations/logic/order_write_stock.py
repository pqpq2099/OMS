from __future__ import annotations

# =============================================================================
# [DEPRECATED — 舊式直接寫入路徑，已由 RPC transaction 取代，禁止呼叫]
# 正式寫入路徑：
#   order_write._save_order_entry
#   → order_write_rpc.build_order_write_rpc_payload
#   → service_order_rpc.rpc_save_order_transaction (Supabase RPC)
# 此模組僅保留歷史參照，write_stocktake_section() 在呼叫時會立即拋出 RuntimeError。
# =============================================================================
_DEPRECATED_LEGACY_PATH = True

from shared.services.service_order_core import norm, safe_float
from operations.logic.order_errors import UserDisplayError
from shared.services.service_id import allocate_stocktake_id
from shared.services.data_backend import append_rows_by_header as sheet_append, get_header as sheet_get_header
from operations.logic.order_write_utils import _update_row_by_id, _upsert_detail_rows_by_parent, _write_audit_log
from shared.utils.utils_units import convert_to_base


def write_stocktake_section(
    *,
    submit_rows,
    vendor_items,
    conversions_df,
    store_id,
    vendor_id,
    record_date,
    existing_stocktake_id: str = "",
    is_initial_stock: bool = False,
    now,
    user_id,
):
    raise RuntimeError(
        "[DEPRECATED] write_stocktake_section 為舊式直接寫入路徑，已停用。"
        " 正式路徑：order_write._save_order_entry"
        " → order_write_rpc.build_order_write_rpc_payload"
        " → service_order_rpc.rpc_save_order_transaction"
    )
    stocktake_rows = []
    for r in submit_rows:
        item_id = norm(r.get("item_id", ""))
        if not item_id:
            continue
        stocktake_rows.append(
            {
                "item_id": item_id,
                "item_name": r.get("item_name", ""),
                "stock_qty": safe_float(r.get("stock_qty", 0)),
                "stock_unit": norm(r.get("stock_unit", "")),
            }
        )

    stocktake_id = norm(existing_stocktake_id)
    stocktake_main_changed = False
    stocktake_line_changed = False

    if stocktake_rows:
        stocktake_header = sheet_get_header("stocktakes")
        stl_header = sheet_get_header("stocktake_lines")

        if stocktake_id:
            stocktake_main_changed = _update_row_by_id(
                "stocktakes",
                "stocktake_id",
                stocktake_id,
                {
                    "store_id": store_id,
                    "vendor_id": vendor_id,
                    "stocktake_date": str(record_date),
                    "status": "done",
                    "note": "initial_stock" if is_initial_stock else f"vendor={vendor_id}",
                    "updated_at": now,
                    "updated_by": user_id,
                },
            )
        else:
            stocktake_id = allocate_stocktake_id()
            stocktake_main_row = {c: "" for c in stocktake_header}
            defaults = {
                "stocktake_id": stocktake_id,
                "store_id": store_id,
                "vendor_id": vendor_id,
                "stocktake_date": str(record_date),
                "status": "done",
                "note": "initial_stock" if is_initial_stock else f"vendor={vendor_id}",
                "created_at": now,
                "created_by": user_id,
            }
            for k, v in defaults.items():
                if k in stocktake_main_row:
                    stocktake_main_row[k] = v
            sheet_append("stocktakes", stocktake_header, [stocktake_main_row])
            stocktake_main_changed = True

        stock_line_rows = []
        for r in stocktake_rows:
            try:
                stock_base_qty, stock_base_unit = convert_to_base(
                    item_id=r["item_id"],
                    qty=r["stock_qty"],
                    from_unit=r["stock_unit"],
                    items_df=vendor_items,
                    conversions_df=conversions_df,
                    as_of_date=record_date,
                )
            except Exception as e:
                raise UserDisplayError(f"{r['item_name']} stock conversion failed: {e}")

            row_dict = {c: "" for c in stl_header}
            defaults_line = {
                "stocktake_id": stocktake_id,
                "store_id": store_id,
                "vendor_id": vendor_id,
                "item_id": r["item_id"],
                "item_name": r["item_name"],
                "qty": str(r["stock_qty"]),
                "stock_qty": str(r["stock_qty"]),
                "unit_id": r["stock_unit"],
                "stock_unit": r["stock_unit"],
                "stock_unit_id": r["stock_unit"],
                "base_qty": str(round(stock_base_qty, 3)),
                "base_unit": stock_base_unit,
                "updated_at": now,
                "updated_by": user_id,
                "created_at": now,
                "created_by": user_id,
            }
            for k, v in defaults_line.items():
                if k in row_dict:
                    row_dict[k] = v
            stock_line_rows.append(row_dict)

        stocktake_line_changed = _upsert_detail_rows_by_parent(
            sheet_name="stocktake_lines",
            parent_field="stocktake_id",
            parent_id=stocktake_id,
            line_id_field="stocktake_line_id",
            item_rows=stock_line_rows,
            allocate_key="stocktake_lines",
        )
        if stocktake_main_changed or stocktake_line_changed:
            _write_audit_log(
                action="update_stocktake" if existing_stocktake_id else "create_stocktake",
                table_name="stocktakes",
                entity_id=stocktake_id,
                note=f"store={store_id}, vendor={vendor_id}, date={record_date}",
            )

    return {
        "stocktake_id": stocktake_id,
        "stocktake_main_changed": stocktake_main_changed,
        "stocktake_line_changed": stocktake_line_changed,
    }
