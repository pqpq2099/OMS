from __future__ import annotations

from shared.services.service_order_core import norm, safe_float, get_base_unit_cost
from operations.logic.order_errors import UserDisplayError
from shared.services.service_id import allocate_purchase_order_id
from shared.services.data_backend import append_rows_by_header as sheet_append, get_header as sheet_get_header, read_table as sheet_read
from operations.logic.order_query import get_existing_order_maps
from operations.logic.order_write_utils import _update_row_by_id, _upsert_detail_rows_by_parent, _write_audit_log
from shared.utils.utils_units import convert_to_base


def write_purchase_order_section(
    *,
    submit_rows,
    vendor_items,
    conversions_df,
    store_id,
    vendor_id,
    record_date,
    delivery_date,
    existing_po_id: str = "",
    now,
    user_id,
):
    prices_df = sheet_read("prices")
    order_rows = [r for r in submit_rows if safe_float(r["order_qty"]) > 0]

    po_id = norm(existing_po_id)
    po_main_changed = False
    po_line_changed = False

    po_header = sheet_get_header("purchase_orders")
    pol_header = sheet_get_header("purchase_order_lines")

    if po_id:
        status_value = "draft" if order_rows else "cancelled"
        po_main_changed = _update_row_by_id(
            "purchase_orders",
            "po_id",
            po_id,
            {
                "store_id": store_id,
                "vendor_id": vendor_id,
                "po_date": str(record_date),
                "order_date": str(record_date),
                "expected_date": str(delivery_date),
                "delivery_date": str(delivery_date),
                "status": status_value,
                "updated_at": now,
                "updated_by": user_id,
            },
        )
    elif order_rows:
        po_id = allocate_purchase_order_id()
        po_row = {c: "" for c in po_header}
        defaults_po = {
            "po_id": po_id,
            "po_date": str(record_date),
            "store_id": store_id,
            "vendor_id": vendor_id,
            "order_date": str(record_date),
            "expected_date": str(delivery_date),
            "delivery_date": str(delivery_date),
            "status": "draft",
            "created_at": now,
            "created_by": user_id,
        }
        for k, v in defaults_po.items():
            if k in po_row:
                po_row[k] = v
        sheet_append("purchase_orders", po_header, [po_row])
        po_main_changed = True

    if po_id:
        po_line_rows = []
        existing_qty_map, existing_unit_map = get_existing_order_maps(po_id)
        target_item_ids = {norm(r.get("item_id", "")) for r in submit_rows if norm(r.get("item_id", ""))}

        existing_line_item_ids = {
            norm(k) for k in list(existing_qty_map.keys()) + list(existing_unit_map.keys()) if norm(k)
        }

        for r in submit_rows:
            item_id = norm(r.get("item_id", ""))
            if item_id not in target_item_ids:
                continue

            order_qty = safe_float(r.get("order_qty", 0))
            order_unit = norm(r.get("order_unit", ""))
            item_name = r.get("item_name", "")

            if order_qty <= 0 and item_id not in existing_line_item_ids:
                continue

            if order_qty > 0:
                try:
                    order_base_qty, order_base_unit = convert_to_base(
                        item_id=r["item_id"],
                        qty=order_qty,
                        from_unit=order_unit,
                        items_df=vendor_items,
                        conversions_df=conversions_df,
                        as_of_date=record_date,
                    )
                except Exception as e:
                    raise UserDisplayError(f"{item_name} order conversion failed: {e}")

                base_unit_cost = get_base_unit_cost(
                    item_id=r["item_id"],
                    target_date=record_date,
                    items_df=vendor_items,
                    prices_df=prices_df,
                    conversions_df=conversions_df,
                )
                if base_unit_cost is None or float(base_unit_cost) <= 0:
                    raise UserDisplayError(f"{item_name} missing valid unit price")

                line_amount = round(float(order_base_qty) * float(base_unit_cost), 1)
                order_unit_price = round(line_amount / float(order_qty), 4) if float(order_qty) > 0 else 0
            else:
                order_base_qty = 0
                order_base_unit = ""
                line_amount = 0
                order_unit_price = 0
                if not order_unit:
                    order_unit = norm(existing_unit_map.get(r["item_id"], ""))

            row_dict = {c: "" for c in pol_header}
            defaults_pol = {
                "po_id": po_id,
                "store_id": store_id,
                "vendor_id": vendor_id,
                "item_id": r["item_id"],
                "item_name": item_name,
                "qty": str(order_qty),
                "order_qty": str(order_qty),
                "unit_id": order_unit,
                "order_unit": order_unit,
                "base_qty": str(round(order_base_qty, 3)),
                "base_unit": order_base_unit,
                "unit_price": str(order_unit_price),
                "amount": str(line_amount),
                "delivery_date": str(delivery_date),
                "updated_at": now,
                "updated_by": user_id,
                "created_at": now,
                "created_by": user_id,
            }
            for k, v in defaults_pol.items():
                if k in row_dict:
                    row_dict[k] = v
            po_line_rows.append(row_dict)

        po_line_changed = _upsert_detail_rows_by_parent(
            sheet_name="purchase_order_lines",
            parent_field="po_id",
            parent_id=po_id,
            line_id_field="po_line_id",
            item_rows=po_line_rows,
            allocate_key="purchase_order_lines",
        )
        if po_main_changed or po_line_changed:
            _write_audit_log(
                action="update_purchase_order" if existing_po_id else "create_purchase_order",
                table_name="purchase_orders",
                entity_id=po_id,
                note=f"store={store_id}, vendor={vendor_id}, order_date={record_date}, delivery_date={delivery_date}",
            )

    return {
        "po_id": po_id,
        "po_main_changed": po_main_changed,
        "po_line_changed": po_line_changed,
    }
