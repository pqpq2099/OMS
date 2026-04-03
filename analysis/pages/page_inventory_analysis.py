from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from analysis.logic.report_view_model import (
    ALL_VENDORS,
    build_analysis_all_vendor_view,
    build_analysis_period_vendor_detail_view,
    build_analysis_single_day_vendor_detail_view,
    build_analysis_upstream_data,
)
from ui_text import t

from .shared import load_report_shared_tables, render_report_dataframe

_ALL_VENDOR_CFG = {
    "廠商": st.column_config.TextColumn(width="medium"),
    "進貨金額": st.column_config.NumberColumn(format="%.1f", width="small"),
    "庫存金額": st.column_config.NumberColumn(format="%.1f", width="small"),
}

_PERIOD_VENDOR_CFG = {
    "日期": st.column_config.TextColumn(width="small"),
    "廠商": st.column_config.TextColumn(width="medium"),
    "這次進貨金額": st.column_config.NumberColumn(format="%.1f", width="small"),
    "這次庫存金額": st.column_config.NumberColumn(format="%.1f", width="small"),
}

_SINGLE_VENDOR_CFG = {
    "日期": st.column_config.TextColumn(width="small"),
    "品項": st.column_config.TextColumn(width="medium"),
    "這次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
    "這次叫貨": st.column_config.NumberColumn(format="%.1f", width="small"),
}


def page_inventory_analysis():
    st.title(f"📊 {t('title_analysis')}")

    mode = st.session_state.get("ana_mode")

    if mode is None:
        _render_landing()
        return

    if mode == "period":
        _render_period_mode()
    else:
        _render_single_day_mode()


# ── 入口頁 ──────────────────────────────────────────────────────────────────

def _render_landing():
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📅 期間庫存與進貨", use_container_width=True, key="ana_enter_period"):
            st.session_state.ana_mode = "period"
            st.rerun()
    with c2:
        if st.button("📌 單日庫存與進貨", use_container_width=True, key="ana_enter_single"):
            st.session_state.ana_mode = "single"
            st.rerun()
    st.markdown("---")
    if st.button(f"⬅️ {t('back_to_menu')}", use_container_width=True, key="ana_back_landing"):
        st.session_state.step = "select_vendor"
        st.rerun()


# ── 期間模式 ─────────────────────────────────────────────────────────────────

def _render_period_mode():
    st.subheader("📅 期間庫存與進貨")
    c1, c2 = st.columns(2)
    start = c1.date_input(t("start_date"), value=date.today() - timedelta(days=14), key="ana_p_start")
    end = c2.date_input(t("end_date"), value=date.today(), key="ana_p_end")

    shared_tables = load_report_shared_tables()
    upstream = build_analysis_upstream_data(st.session_state.store_id, start, end, shared_tables)

    all_vendor_view = build_analysis_all_vendor_view(upstream)
    vendor_options = all_vendor_view["vendor_options"]

    if not vendor_options or (upstream.get("hist_df") is None or upstream["hist_df"].empty) and all_vendor_view["table_df"].empty:
        st.warning(t("analysis_no_records"))
        _back_to_landing()
        return

    selected_vendor = st.selectbox(
        f"🏢 {t('select_vendor')}",
        options=vendor_options,
        index=0,
        key="ana_p_vendor",
    )

    st.markdown("---")

    if selected_vendor == ALL_VENDORS:
        c_m1, c_m2 = st.columns(2)
        c_m1.metric(t("metric_total_purchase"), f"{all_vendor_view['total_purchase']:,.1f}")
        c_m2.metric(t("metric_total_stock"), f"{all_vendor_view['total_stock']:,.1f}")
        if all_vendor_view["table_df"].empty:
            st.info(t("current_condition_no_amount"))
        else:
            render_report_dataframe(all_vendor_view["table_df"], column_config=_ALL_VENDOR_CFG)
    else:
        detail = build_analysis_period_vendor_detail_view(upstream, selected_vendor)
        c_m1, c_m2 = st.columns(2)
        c_m1.metric(t("metric_total_purchase"), f"{detail['total_purchase']:,.1f}")
        c_m2.metric(t("metric_total_stock"), f"{detail['total_stock']:,.1f}")
        if detail["table_df"].empty:
            st.info(t("current_vendor_no_data"))
        else:
            render_report_dataframe(detail["table_df"], column_config=_PERIOD_VENDOR_CFG)

    _back_to_landing()


# ── 單日模式 ─────────────────────────────────────────────────────────────────

def _render_single_day_mode():
    st.subheader("📌 單日庫存與進貨")
    selected_date = st.date_input(t("date"), value=date.today(), key="ana_s_date")

    shared_tables = load_report_shared_tables()
    upstream = build_analysis_upstream_data(st.session_state.store_id, selected_date, selected_date, shared_tables)

    all_vendor_view = build_analysis_all_vendor_view(upstream)
    vendor_options = all_vendor_view["vendor_options"]

    if not vendor_options and all_vendor_view["table_df"].empty:
        st.warning(t("analysis_no_records"))
        _back_to_landing()
        return

    selected_vendor = st.selectbox(
        f"🏢 {t('select_vendor')}",
        options=vendor_options,
        index=0,
        key="ana_s_vendor",
    )

    st.markdown("---")

    if selected_vendor == ALL_VENDORS:
        c_m1, c_m2 = st.columns(2)
        c_m1.metric(t("metric_total_purchase"), f"{all_vendor_view['total_purchase']:,.1f}")
        c_m2.metric(t("metric_total_stock"), f"{all_vendor_view['total_stock']:,.1f}")
        if all_vendor_view["table_df"].empty:
            st.info(t("current_condition_no_amount"))
        else:
            render_report_dataframe(all_vendor_view["table_df"], column_config=_ALL_VENDOR_CFG)
    else:
        # For metrics, use vendor totals from the all_vendor_view aggregation
        vendor_row = all_vendor_view["table_df"]
        if not vendor_row.empty and "廠商" in vendor_row.columns:
            vendor_row = vendor_row[vendor_row["廠商"].astype(str).str.strip() == str(selected_vendor).strip()]
        total_purchase = float(vendor_row["進貨金額"].sum()) if not vendor_row.empty and "進貨金額" in vendor_row.columns else 0.0
        total_stock = float(vendor_row["庫存金額"].sum()) if not vendor_row.empty and "庫存金額" in vendor_row.columns else 0.0
        c_m1, c_m2 = st.columns(2)
        c_m1.metric(t("metric_total_purchase"), f"{total_purchase:,.1f}")
        c_m2.metric(t("metric_total_stock"), f"{total_stock:,.1f}")
        detail = build_analysis_single_day_vendor_detail_view(upstream, selected_vendor)
        if detail["table_df"].empty:
            st.info(t("current_vendor_no_data"))
        else:
            render_report_dataframe(detail["table_df"], column_config=_SINGLE_VENDOR_CFG)

    _back_to_landing()


# ── 共用：返回入口 ────────────────────────────────────────────────────────────

def _back_to_landing():
    st.markdown("---")
    if st.button(f"⬅️ {t('back')}", use_container_width=True, key="ana_back_mode"):
        st.session_state.ana_mode = None
        st.rerun()
