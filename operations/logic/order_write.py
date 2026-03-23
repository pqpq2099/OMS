from __future__ import annotations

import time

import streamlit as st

from oms_core import _norm, _now_ts
from operations.logic.order_write_po import write_purchase_order_section
from operations.logic.order_write_stock import write_stocktake_section
from services.service_sheet import sheet_bust_cache


def _is_rate_limit_error(exc) -> bool:
    exc_text = str(exc)
    return (
        "429" in exc_text
        or "Too Many Requests" in exc_text
        or "rate limit" in exc_text.lower()
    )


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
    now = _now_ts()
    user_id = _norm(st.session_state.get("login_user_id", "")) or "SYSTEM"

    write_stocktake_section(
        submit_rows=submit_rows,
        vendor_items=vendor_items,
        conversions_df=conversions_df,
        store_id=store_id,
        vendor_id=vendor_id,
        record_date=record_date,
        existing_stocktake_id=existing_stocktake_id,
        is_initial_stock=is_initial_stock,
        now=now,
        user_id=user_id,
    )

    for attempt in range(2):
        try:
            po_result = write_purchase_order_section(
                submit_rows=submit_rows,
                vendor_items=vendor_items,
                conversions_df=conversions_df,
                store_id=store_id,
                vendor_id=vendor_id,
                record_date=record_date,
                delivery_date=delivery_date,
                existing_po_id=existing_po_id,
                now=now,
                user_id=user_id,
            )
            break
        except Exception as exc:
            if attempt == 0 and _is_rate_limit_error(exc):
                time.sleep(1.0)
                continue
            raise

    sheet_bust_cache()
    return po_result["po_id"]
