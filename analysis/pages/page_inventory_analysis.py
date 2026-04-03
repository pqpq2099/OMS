from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from analysis.logic.report_view_model import (
    ALL_VENDORS,
    DISPLAY_MODE_FULL,
    DISPLAY_MODE_MOBILE,
    build_analysis_detail_section,
    build_analysis_page_view_model,
    build_analysis_vendor_summary_section,
)
from ui_text import t

from .shared import display_mode_selector, load_report_shared_tables, render_report_dataframe


def page_inventory_analysis():
    st.title(f"📊 {t('title_analysis')}")
    c_date1, c_date2 = st.columns(2)
    start = c_date1.date_input(t("start_date"), value=date.today() - timedelta(days=14), key="ana_start")
    end = c_date2.date_input(t("end_date"), value=date.today(), key="ana_end")
    shared_tables = load_report_shared_tables()
    preview_model = build_analysis_page_view_model(
        st.session_state.store_id,
        start,
        end,
        ALL_VENDORS,
        DISPLAY_MODE_MOBILE,
        shared_tables,
    )
    if preview_model["hist_df"].empty and preview_model["purchase_filt"].empty:
        st.warning(t("analysis_no_records"))
        if st.button(f"⬅️ {t('back_to_menu')}", use_container_width=True, key="back_from_analysis_no_data"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    st.markdown("---")
    selected_vendor = st.selectbox(
        f"🏢 {t('select_vendor')}",
        options=preview_model["vendor_options"],
        index=0,
        key="ana_vendor_filter",
    )
    display_mode = display_mode_selector("analysis_display_mode")
    model = build_analysis_page_view_model(st.session_state.store_id, start, end, selected_vendor, display_mode, shared_tables)
    st.markdown("---")
    c_amt1, c_amt2 = st.columns(2)
    c_amt1.metric(t("metric_total_purchase"), f"{model['total_purchase_amount']:,.1f}")
    c_amt2.metric(t("metric_total_stock"), f"{model['total_stock_amount']:,.1f}")

    if selected_vendor == ALL_VENDORS:
        st.subheader(f"📋 {t('analysis_all_vendor_summary')}")
        if model["vendor_summary"].empty:
            st.info(t("current_condition_no_amount"))
        else:
            vendor_summary_section = build_analysis_vendor_summary_section(model, display_mode)
            vendor_summary = vendor_summary_section["show_df"]
            st.download_button(
                t("download_csv"),
                vendor_summary_section["csv_payload"],
                file_name=f"進銷存分析_全部廠商_{start}_{end}.csv",
                mime="text/csv",
                use_container_width=False,
                key="download_analysis_all_vendors",
            )
            render_report_dataframe(
                vendor_summary,
                column_config={
                    "日期": st.column_config.TextColumn(width="small"),
                    "廠商": st.column_config.TextColumn(width="medium"),
                    "進貨金額": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "庫存金額": st.column_config.NumberColumn(format="%.1f", width="small"),
                },
            )
        if st.button(f"⬅️ {t('back_to_menu')}", use_container_width=True, key="back_from_analysis_all"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    st.subheader(f"📦 {selected_vendor} {t('analysis_vendor_detail')}")
    if model["detail_df"].empty:
        st.info(t("current_vendor_no_data"))
    else:
        detail_section = build_analysis_detail_section(model)
        show_df = detail_section["show_df"]
        cfg = (
            {
                "日期": st.column_config.TextColumn(width="small"),
                "品項": st.column_config.TextColumn(width="medium"),
                "庫存金額": st.column_config.NumberColumn(format="%.1f", width="small"),
            }
            if display_mode == DISPLAY_MODE_MOBILE
            else {
                "日期": st.column_config.TextColumn(width="small"),
                "品項": st.column_config.TextColumn(width="medium"),
                "上次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                "期間進貨": st.column_config.NumberColumn(format="%.1f", width="small"),
                "庫存合計": st.column_config.NumberColumn(format="%.1f", width="small"),
                "這次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                "期間消耗": st.column_config.NumberColumn(format="%.1f", width="small"),
                "這次叫貨": st.column_config.NumberColumn(format="%.1f", width="small"),
                "日平均": st.column_config.NumberColumn(format="%.1f", width="small"),
            }
        )
        st.download_button(
            t("download_csv"),
            detail_section["csv_payload"],
            file_name=f"進銷存分析_{selected_vendor}_{start}_{end}.csv",
            mime="text/csv",
            use_container_width=False,
            key="download_analysis_single_vendor",
        )
        render_report_dataframe(show_df, column_config=cfg)
    if st.button(f"⬅️ {t('back_to_menu')}", use_container_width=True, key="back_from_analysis_single"):
        st.session_state.step = "select_vendor"
        st.rerun()
