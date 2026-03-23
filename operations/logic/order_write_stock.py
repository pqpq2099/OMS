from __future__ import annotations

from oms_core import _norm, _safe_float
from operations.logic.order_errors import UserDisplayError
from services.service_id import allocate_ids_map
from services.service_sheet import sheet_append, sheet_get_header
from operations.logic.order_write_utils import _update_row_by_id, _upsert_detail_rows_by_parent, _write_audit_log
from utils.utils_units import convert_to_base


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
    stocktake_rows = []
    for r in submit_rows:
        item_id = _norm(r.get("item_id", ""))
        if not item_id:
            continue
        stocktake_rows.append(
            {
                "item_id": item_id,
                "item_name": r.get("item_name", ""),
                "stock_qty": _safe_float(r.get("stock_qty", 0)),
                "stock_unit": _norm(r.get("stock_unit", "")),
            }
        )

    stocktake_id = _norm(existing_stocktake_id)
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
            id_map = allocate_ids_map({"stocktakes": 1})
            stocktake_id = id_map["stocktakes"][0]
            stocktake_main_row = {c: "" for c in stocktake_header}
            defaults = {
                "stocktake_id": stocktake_id,
                "store_id": store_id,
                "vendor_id": vendor_id,
                "stocktake_date": str(record_date),
                "stocktake_type": "initial" if is_initial_stock else "regular",
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
