from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from oms_core import _get_active_df, _label_store, _label_vendor, read_table
from operations.logic.order_decision import build_item_decision_data
from operations.logic.order_query import (
    find_existing_operation_ids,
    get_existing_order_maps,
    get_existing_stock_map,
    load_order_page_tables,
    load_selector_tables,
)


def weekday_option_from_date(
    target_date: date | None,
    weekday_options: list[str],
    fallback: date | None = None,
) -> str:
    ref = target_date or fallback or date.today()
    return weekday_options[ref.weekday()]


def delivery_date_from_weekday(
    record_date: date,
    weekday_option: str,
    weekday_options: list[str],
) -> date:
    text = str(weekday_option or "").strip().replace("星期", "週")
    if text not in weekday_options:
        return record_date

    target_weekday = weekday_options.index(text)
    current_weekday = record_date.weekday()
    delta = target_weekday - current_weekday
    if delta < 0:
        delta += 7
    return record_date + timedelta(days=delta)


def is_initial_stocktake(store_id: str, stocktakes_df: pd.DataFrame) -> bool:
    if stocktakes_df.empty or "store_id" not in stocktakes_df.columns:
        return True

    store_stocktakes = stocktakes_df[
        stocktakes_df["store_id"].astype(str).str.strip() == str(store_id).strip()
    ]
    return len(store_stocktakes) == 0


def get_active_vendor_items(items_df: pd.DataFrame, vendor_id: str) -> pd.DataFrame:
    if items_df.empty or "default_vendor_id" not in items_df.columns:
        return pd.DataFrame()

    vendor_items = items_df[
        items_df["default_vendor_id"].astype(str).str.strip() == str(vendor_id).strip()
    ].copy()
    return vendor_items.reset_index(drop=True)


def get_store_selection_view_model() -> dict:
    selector_tables = load_selector_tables()
    stores_df = _get_active_df(selector_tables["stores"])
    login_role_id = str(st.session_state.get("login_role_id", "")).strip().lower()
    login_store_scope = str(st.session_state.get("login_store_scope", "")).strip()

    error_message = ""
    if not stores_df.empty:
        stores_df = stores_df.copy()
        if login_role_id not in ["owner", "admin", "test_admin"]:
            if not login_store_scope or login_store_scope == "ALL":
                error_message = "目前帳號缺少可用門市範圍設定。"
                stores_df = stores_df.iloc[0:0].copy()
            else:
                stores_df = stores_df[
                    stores_df["store_id"].astype(str).str.strip() == login_store_scope
                ].copy()
                if stores_df.empty:
                    error_message = "目前帳號的 store_scope 無法對應到有效門市。"

    if not stores_df.empty:
        stores_df["store_label"] = stores_df.apply(_label_store, axis=1)

    return {
        "stores_df": stores_df,
        "error_message": error_message,
    }


def get_vendor_selection_view_model(record_date: date, store_id: str) -> dict:
    selector_tables = load_selector_tables()
    vendors_df = _get_active_df(selector_tables["vendors"])
    items_df = _get_active_df(selector_tables["items"])

    vendors = pd.DataFrame()
    if not vendors_df.empty and not items_df.empty:
        item_vendor_ids = set(
            items_df.get("default_vendor_id", pd.Series(dtype=str))
            .astype(str)
            .str.strip()
        )
        vendors = vendors_df[
            vendors_df["vendor_id"].astype(str).str.strip().isin(item_vendor_ids)
        ].copy()
        if not vendors.empty:
            vendors["vendor_label"] = vendors.apply(_label_vendor, axis=1)
            vendors = vendors.sort_values(by=["vendor_label"], ascending=True).reset_index(
                drop=True
            )

    return {
        "record_date": record_date,
        "store_id": store_id,
        "vendors_df": vendors_df,
        "items_df": items_df,
        "vendors": vendors,
    }


def build_order_entry_view_model(
    *,
    store_id: str,
    vendor_id: str,
    record_date: date,
    weekday_options: list[str],
) -> dict:
    initial_stocktakes_df = read_table("stocktakes")
    is_initial_stock = is_initial_stocktake(store_id, initial_stocktakes_df)

    page_tables = load_order_page_tables()
    items_df = _get_active_df(page_tables["items"])
    prices_df = page_tables["prices"]
    conversions_df = _get_active_df(page_tables["unit_conversions"])
    stocktakes_df = page_tables["stocktakes"]
    stocktake_lines_df = page_tables["stocktake_lines"]

    has_items = not items_df.empty
    has_default_vendor_column = "default_vendor_id" in items_df.columns if has_items else False
    vendor_items = (
        get_active_vendor_items(items_df, vendor_id)
        if has_items and has_default_vendor_column
        else pd.DataFrame()
    )

    existing_ids = find_existing_operation_ids(
        store_id=store_id,
        vendor_id=vendor_id,
        record_date=record_date,
    )
    existing_stock_map = get_existing_stock_map(existing_ids.get("stocktake_id", ""))
    existing_order_qty_map, existing_order_unit_map = get_existing_order_maps(
        existing_ids.get("po_id", "")
    )
    existing_delivery_option = weekday_option_from_date(
        existing_ids.get("delivery_date"),
        weekday_options,
        record_date + timedelta(days=1),
    )

    decision = {
        "item_meta": {},
        "ref_df": pd.DataFrame(),
    }
    if not vendor_items.empty:
        decision = build_item_decision_data(
            vendor_items=vendor_items,
            prices_df=prices_df,
            conversions_df=conversions_df,
            stocktakes_df=stocktakes_df,
            stocktake_lines_df=stocktake_lines_df,
            store_id=store_id,
            vendor_id=vendor_id,
            record_date=record_date,
            existing_stock_map=existing_stock_map,
            existing_order_qty_map=existing_order_qty_map,
            existing_order_unit_map=existing_order_unit_map,
        )

    return {
        "is_initial_stock": is_initial_stock,
        "items_df_empty": items_df.empty,
        "items_missing_default_vendor_id": has_items and not has_default_vendor_column,
        "vendor_items": vendor_items,
        "page_tables": page_tables,
        "conversions_df": conversions_df,
        "existing_ids": existing_ids,
        "existing_delivery_option": existing_delivery_option,
        "is_edit_mode": bool(existing_ids.get("stocktake_id") or existing_ids.get("po_id")),
        "item_meta": decision["item_meta"],
        "ref_df": decision["ref_df"],
    }
