from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from analysis.logic.report_view_model import ALL_ITEMS, ALL_VENDORS, DISPLAY_MODE_FULL, build_history_detail_section, build_history_page_view_model, resolve_history_filter_state
from ui_text import t

from .shared import load_report_shared_tables, render_report_dataframe


def page_order_history():
    st.markdown(
        """
        <style>
        [data-testid='stMainBlockContainer'] { max-width: 95% !important; padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
        [data-testid='stDataFrame'] [role='gridcell'] { padding: 1px 2px !important; line-height: 1.0 !important; }
        [data-testid='stDataFrame'] [role='columnheader'] { padding: 2px 2px !important; font-size: 10px !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title(f"📜 {st.session_state.store_name} {t('title_view_history')}")
    c_h_date1, c_h_date2 = st.columns(2)
    h_start = c_h_date1.date_input(t("start_date"), value=date.today() - timedelta(days=30), key="hist_start_date")
    h_end = c_h_date2.date_input(t("end_date"), value=date.today(), key="hist_end_date")
    shared_tables = load_report_shared_tables()
    display_mode = DISPLAY_MODE_FULL
    base_model = build_history_page_view_model(st.session_state.store_id, h_start, h_end, ALL_VENDORS, ALL_ITEMS, display_mode, shared_tables)
    if base_model["hist_df"].empty:
        st.info(t("history_no_record"))
        if st.button(f"⬅️ {t('back')}", use_container_width=True, key="back_hist_empty"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    sel_v = st.selectbox(f"🏢 {t('history_vendor_filter')}", options=base_model["vendor_options"], index=0, key="hist_vendor_filter")
    option_model = build_history_page_view_model(st.session_state.store_id, h_start, h_end, sel_v, ALL_ITEMS, display_mode, shared_tables)
    all_i = option_model["item_options"]
    filter_state = resolve_history_filter_state(
        selected_vendor=sel_v,
        previous_vendor=st.session_state.get("hist_vendor_filter_prev", sel_v),
        current_item_filter=st.session_state.get("hist_item_filter", ALL_ITEMS),
        item_options=all_i,
        default_item=ALL_ITEMS,
    )
    st.session_state.hist_vendor_filter_prev = filter_state["previous_vendor"]
    st.session_state.hist_item_filter = filter_state["item_filter"]
    sel_i = st.selectbox(f"🏷️ {t('history_item_filter')}", options=all_i, key="hist_item_filter")
    model = build_history_page_view_model(st.session_state.store_id, h_start, h_end, sel_v, sel_i, display_mode, shared_tables)
    detail_section = build_history_detail_section(model)
    detail_df = detail_section["detail_df"]
    if detail_df.empty:
        st.caption(t("history_no_data"))
    elif sel_v == ALL_VENDORS:
        st.caption(t("history_all_vendor_hide"))
    else:
        show_df = detail_section["show_df"]
        cfg = {
            "日期顯示": st.column_config.TextColumn(t("date"), width="small"),
            "品項": st.column_config.TextColumn(width="medium"),
            "上次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
            "期間進貨": st.column_config.NumberColumn(format="%.1f", width="small"),
            "庫存合計": st.column_config.NumberColumn(format="%.1f", width="small"),
            "這次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
            "期間消耗": st.column_config.NumberColumn(format="%.1f", width="small"),
            "這次叫貨": st.column_config.NumberColumn(format="%.1f", width="small"),
            "日平均": st.column_config.NumberColumn(format="%.1f", width="small"),
        }
        st.download_button(
            t("download_csv"),
            detail_section["csv_payload"],
            file_name=f"歷史叫貨紀錄_{sel_v}_{h_start}_{h_end}.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_history_csv",
        )
        render_report_dataframe(show_df, column_config=cfg)
    if st.button(f"⬅️ {t('back')}", use_container_width=True, key="back_hist_final"):
        st.session_state.step = "select_vendor"
        st.rerun()
