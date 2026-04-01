from __future__ import annotations

from operations.logic.order_decision import (
    build_item_decision_data,
    convert_metric_base_to_order_display_qty,
    convert_metric_base_to_stock_display_qty,
)
from operations.logic.order_query import (
    clear_order_page_tables_cache,
    clear_selector_tables_cache,
    find_existing_operation_ids,
    get_existing_order_maps,
    get_existing_stock_map,
    load_order_page_tables,
    load_selector_tables,
)
from operations.logic.order_validation import validate_order_submission
from operations.logic.order_view_model import (
    build_order_edit_caption,
    build_order_entry_view_model,
    build_order_item_cards_view_model,
    build_order_reference_display_df,
    delivery_date_from_weekday,
    get_active_vendor_items,
    get_store_selection_view_model,
    get_vendor_selection_view_model,
    is_initial_stocktake,
    weekday_option_from_date,
)



def submit_order_entry(
    *,
    submit_rows: list[dict],
    vendor_items,
    conversions_df,
    store_id: str,
    vendor_id: str,
    record_date,
    delivery_date,
    existing_stocktake_id: str,
    existing_po_id: str,
    is_initial_stock: bool,
) -> dict:
    errors = validate_order_submission(
        submit_rows=submit_rows,
        vendor_items=vendor_items,
        conversions_df=conversions_df,
        record_date=record_date,
        is_initial_stock=is_initial_stock,
    )
    if errors:
        return {"ok": False, "errors": errors, "po_id": ""}

    from operations.logic.order_write import _save_order_entry

    po_id = _save_order_entry(
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
    return {"ok": True, "errors": [], "po_id": po_id}
