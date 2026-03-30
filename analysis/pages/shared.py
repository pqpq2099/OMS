from __future__ import annotations

from datetime import date

import streamlit as st

from shared.services.service_reports import render_report_dataframe
from analysis.logic.report_query import load_report_shared_tables
from analysis.logic.report_view_model import (
    build_csv_download_payload,
    ALL_ITEMS,
    ALL_VENDORS,
    DISPLAY_MODE_FULL,
    DISPLAY_MODE_MOBILE,
    build_export_view_model,
    format_mmdd_column,
    get_store_scope_options,
    short_item_name,
)
from ui_text import t


def display_mode_selector(key: str) -> str:
    return st.radio(t("display_mode"), options=[DISPLAY_MODE_MOBILE, DISPLAY_MODE_FULL], horizontal=True, key=key)


def download_csv_block(preview, filename: str):
    if preview.empty:
        st.info(t("no_export_data"))
        return
    st.download_button(
        t("download_csv"),
        build_csv_download_payload(preview),
        file_name=filename,
        mime="text/csv",
        use_container_width=True,
        key=f"download_{filename}",
    )
    render_report_dataframe(preview)


def select_export_store(key: str):
    shared_tables = load_report_shared_tables()
    store_ids, store_label_map = get_store_scope_options(
        shared_tables,
        str(st.session_state.get("store_id", "")).strip(),
        str(st.session_state.get("store_name", "")).strip(),
        str(st.session_state.get("login_role_id", "")).strip(),
    )
    if not store_ids:
        return "", ""
    current_store_id = str(st.session_state.get("store_id", "")).strip()
    default_index = store_ids.index(current_store_id) if current_store_id in store_ids else 0
    selected_store_id = st.selectbox(
        t("select_store"),
        options=store_ids,
        index=default_index,
        format_func=lambda x: store_label_map.get(x, x),
        key=key,
    )
    return selected_store_id, store_label_map.get(selected_store_id, selected_store_id)


__all__ = [
    "ALL_ITEMS",
    "ALL_VENDORS",
    "DISPLAY_MODE_FULL",
    "DISPLAY_MODE_MOBILE",
    "build_export_view_model",
    "date",
    "display_mode_selector",
    "download_csv_block",
    "format_mmdd_column",
    "get_store_scope_options",
    "load_report_shared_tables",
    "render_report_dataframe",
    "select_export_store",
    "short_item_name",
    "st",
    "t",
]
