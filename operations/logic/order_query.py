from __future__ import annotations

from datetime import date

from shared.services.service_order_core import norm, parse_date, read_order_table
from operations.logic.order_query_common import (
    ORDER_PAGE_TABLES,
    SELECTOR_TABLES,
    clear_order_page_tables_cache,
    clear_selector_tables_cache,
    load_order_page_tables,
    load_selector_tables,
)
from operations.logic.order_query_po import get_existing_order_maps
from operations.logic.order_query_stock import get_existing_stock_map


def find_existing_operation_ids(store_id: str, vendor_id: str, record_date: date) -> dict:
    result = {
        "stocktake_id": "",
        "po_id": "",
        "delivery_date": None,
    }

    target_date = str(record_date)

    stocktakes_df = read_order_table("stocktakes")
    required_stock_cols = {"store_id", "vendor_id", "stocktake_date", "stocktake_id"}
    if not stocktakes_df.empty and required_stock_cols.issubset(stocktakes_df.columns):
        work = stocktakes_df.copy()
        work["stocktake_date_str"] = work["stocktake_date"].astype(str).str[:10]
        work = work[
            (work["store_id"].astype(str).str.strip() == str(store_id).strip())
            & (work["vendor_id"].astype(str).str.strip() == str(vendor_id).strip())
            & (work["stocktake_date_str"] == target_date)
        ].copy()
        if not work.empty:
            sort_cols = [
                c
                for c in ["updated_at", "created_at", "stocktake_id"]
                if c in work.columns
            ]
            if sort_cols:
                work = work.sort_values(sort_cols, ascending=True)
            result["stocktake_id"] = norm(work.iloc[-1].get("stocktake_id", ""))

    po_df = read_order_table("purchase_orders")
    required_po_cols = {"store_id", "vendor_id", "order_date", "po_id"}
    if not po_df.empty and required_po_cols.issubset(po_df.columns):
        work = po_df.copy()
        work["order_date_str"] = work["order_date"].astype(str).str[:10]
        work = work[
            (work["store_id"].astype(str).str.strip() == str(store_id).strip())
            & (work["vendor_id"].astype(str).str.strip() == str(vendor_id).strip())
            & (work["order_date_str"] == target_date)
        ].copy()
        if not work.empty:
            sort_cols = [c for c in ["updated_at", "created_at", "po_id"] if c in work.columns]
            if sort_cols:
                work = work.sort_values(sort_cols, ascending=True)
            hit = work.iloc[-1]
            result["po_id"] = norm(hit.get("po_id", ""))
            result["delivery_date"] = parse_date(
                hit.get("delivery_date")
            ) or parse_date(hit.get("expected_date"))

    return result
