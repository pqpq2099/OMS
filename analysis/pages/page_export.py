from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from analysis.logic.report_view_model import ALL_ITEMS, ALL_VENDORS
from ui_text import t

from .shared import build_export_view_model, download_csv_block, load_report_shared_tables, select_export_store


def page_export_report():
    st.title(f"📤 {t('title_export')}")
    export_type = st.selectbox(
        t("label_export_type"),
        [t("export_today_purchase_detail"), t("export_analysis"), t("export_history")],
        key="export_type",
    )
    selected_store_id, selected_store_name = select_export_store("export_store_id")
    if not selected_store_id:
        st.warning(t("no_export_store_data"))
        if st.button(f"⬅️ {t('back_to_menu')}", use_container_width=True, key="back_export_no_store"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    c1, c2 = st.columns(2)
    start = c1.date_input(t("start_date"), value=date.today() - timedelta(days=14), key="export_start")
    end = c2.date_input(t("end_date"), value=date.today(), key="export_end")
    shared_tables = load_report_shared_tables()
    option_model = build_export_view_model(export_type, selected_store_id, selected_store_name, start, end, ALL_VENDORS, ALL_ITEMS, shared_tables)
    selected_vendor = st.selectbox(t("select_vendor"), option_model["vendor_options"], key=f"export_vendor_{export_type}")
    selected_item = st.selectbox(t("select_item"), option_model["item_options"], key=f"export_item_{export_type}")
    model = build_export_view_model(export_type, selected_store_id, selected_store_name, start, end, selected_vendor, selected_item, shared_tables)
    st.markdown("---")
    download_csv_block(model["preview"], model["filename"])
    if st.button(f"⬅️ {t('back_to_menu')}", use_container_width=True, key="back_export_center"):
        st.session_state.step = "select_vendor"
        st.rerun()
