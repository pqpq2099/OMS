from __future__ import annotations

import pandas as pd
import streamlit as st

from oms_core import get_table_versions, read_table


ORDER_PAGE_TABLES = (
    "stores",
    "vendors",
    "items",
    "prices",
    "unit_conversions",
    "stocktakes",
    "stocktake_lines",
    "purchase_orders",
    "purchase_order_lines",
)

SELECTOR_TABLES = ("stores", "vendors", "items")


def load_selector_tables() -> dict[str, pd.DataFrame]:
    versions = get_table_versions(SELECTOR_TABLES)
    cache = st.session_state.get("_selector_tables_cache")
    if isinstance(cache, dict) and cache.get("versions") == versions:
        data = cache.get("data", {})
        if data:
            return {k: v.copy() for k, v in data.items()}

    data = {name: read_table(name) for name in SELECTOR_TABLES}
    st.session_state["_selector_tables_cache"] = {
        "versions": versions,
        "data": {k: v.copy() for k, v in data.items()},
    }
    return {k: v.copy() for k, v in data.items()}


def clear_selector_tables_cache():
    st.session_state.pop("_selector_tables_cache", None)


def load_order_page_tables() -> dict[str, pd.DataFrame]:
    versions = get_table_versions(ORDER_PAGE_TABLES)
    cache = st.session_state.get("_order_page_tables_cache")
    if isinstance(cache, dict) and cache.get("versions") == versions:
        data = cache.get("data", {})
        if data:
            return {k: v.copy() for k, v in data.items()}

    data = {name: read_table(name) for name in ORDER_PAGE_TABLES}
    st.session_state["_order_page_tables_cache"] = {
        "versions": versions,
        "data": {k: v.copy() for k, v in data.items()},
    }
    return {k: v.copy() for k, v in data.items()}


def clear_order_page_tables_cache():
    st.session_state.pop("_order_page_tables_cache", None)
