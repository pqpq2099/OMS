from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from oms_core import render_report_dataframe
from operations.logic.report_query import load_report_shared_tables
from operations.logic.report_view_model import (
    ALL_ITEMS,
    ALL_VENDORS,
    DISPLAY_MODE_FULL,
    DISPLAY_MODE_MOBILE,
    build_analysis_page_view_model,
    build_cost_debug_selector_data,
    build_cost_debug_view_model,
    build_export_view_model,
    build_history_page_view_model,
    build_stock_order_compare_view_model,
    format_mmdd_column,
    get_store_scope_options,
    short_item_name,
)
from ui_text import t


def _display_mode_selector(key: str) -> str:
    return st.radio(t("display_mode"), options=[DISPLAY_MODE_MOBILE, DISPLAY_MODE_FULL], horizontal=True, key=key)


def _download_csv_block(preview, filename: str):
    if preview.empty:
        st.info(t("no_export_data"))
        return
    st.download_button(t("download_csv"), preview.to_csv(index=False).encode("utf-8-sig"), file_name=filename, mime="text/csv", use_container_width=True, key=f"download_{filename}")
    render_report_dataframe(preview)


def _select_export_store(key: str):
    shared_tables = load_report_shared_tables()
    store_ids, store_label_map = get_store_scope_options(shared_tables, str(st.session_state.get("store_id", "")).strip(), str(st.session_state.get("store_name", "")).strip(), str(st.session_state.get("login_role_id", "")).strip())
    if not store_ids:
        return "", ""
    current_store_id = str(st.session_state.get("store_id", "")).strip()
    default_index = store_ids.index(current_store_id) if current_store_id in store_ids else 0
    selected_store_id = st.selectbox(t("select_store"), options=store_ids, index=default_index, format_func=lambda x: store_label_map.get(x, x), key=key)
    return selected_store_id, store_label_map.get(selected_store_id, selected_store_id)


def page_stock_order_compare():
    st.title(f"📄 {t('title_stock_order_compare')}")
    store_id = str(st.session_state.get("store_id", "")).strip()
    store_name = str(st.session_state.get("store_name", "")).strip()
    if not store_id:
        st.warning(t("need_select_store"))
        return
    selected_date = st.date_input(t("date"), value=st.session_state.get("record_date", date.today()), key="stock_order_compare_date")
    shared_tables = load_report_shared_tables()
    base_model = build_stock_order_compare_view_model(store_id, selected_date, ALL_VENDORS, shared_tables)
    if not base_model["has_source"] or base_model["preview"].empty:
        st.info(t("no_data_today"))
        return
    selected_vendor = st.selectbox(t("select_vendor"), base_model["vendor_options"], index=0, key="stock_order_compare_vendor")
    preview = build_stock_order_compare_view_model(store_id, selected_date, selected_vendor, shared_tables)["preview"]
    if preview.empty:
        st.info(t("no_non_zero_data_today"))
        return
    st.caption(f"{store_name}｜{selected_date.strftime('%m/%d')}")
    _download_csv_block(preview, f"stock_order_compare_{store_id}_{selected_date}.csv")
    if st.button(f"⬅️ {t('back_to_function_menu')}", use_container_width=True, key="back_from_stock_order_compare"):
        st.session_state.step = "select_vendor"
        st.rerun()


def page_view_history():
    st.markdown("""
        <style>
        [data-testid='stMainBlockContainer'] { max-width: 95% !important; padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
        [data-testid='stDataFrame'] [role='gridcell'] { padding: 1px 2px !important; line-height: 1.0 !important; }
        [data-testid='stDataFrame'] [role='columnheader'] { padding: 2px 2px !important; font-size: 10px !important; }
        </style>
        """, unsafe_allow_html=True)
    st.title(f"📜 {st.session_state.store_name} {t('title_view_history')}")
    c_h_date1, c_h_date2 = st.columns(2)
    h_start = c_h_date1.date_input(t("start_date"), value=date.today() - timedelta(days=30), key="hist_start_date")
    h_end = c_h_date2.date_input(t("end_date"), value=date.today(), key="hist_end_date")
    shared_tables = load_report_shared_tables()
    display_mode = DISPLAY_MODE_MOBILE
    base_model = build_history_page_view_model(st.session_state.store_id, h_start, h_end, ALL_VENDORS, ALL_ITEMS, display_mode, shared_tables)
    if base_model["hist_df"].empty:
        st.info(t("history_no_record"))
        if st.button(f"⬅️ {t('back')}", use_container_width=True, key="back_hist_empty"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return
    sel_v = st.selectbox(f"🏢 {t('history_vendor_filter')}", options=base_model["vendor_options"], index=0, key="hist_vendor_filter")
    if "hist_vendor_filter_prev" not in st.session_state:
        st.session_state.hist_vendor_filter_prev = sel_v
    if st.session_state.hist_vendor_filter_prev != sel_v:
        st.session_state.hist_item_filter = ALL_ITEMS
        st.session_state.hist_vendor_filter_prev = sel_v
    option_model = build_history_page_view_model(st.session_state.store_id, h_start, h_end, sel_v, ALL_ITEMS, display_mode, shared_tables)
    all_i = option_model["item_options"]
    if st.session_state.get("hist_item_filter", ALL_ITEMS) not in all_i:
        st.session_state.hist_item_filter = ALL_ITEMS
    sel_i = st.selectbox(f"🏷️ {t('history_item_filter')}", options=all_i, key="hist_item_filter")
    model = build_history_page_view_model(st.session_state.store_id, h_start, h_end, sel_v, sel_i, display_mode, shared_tables)
    detail_df = model["detail_df"]
    if detail_df.empty:
        st.caption(t("history_no_data"))
    elif sel_v == ALL_VENDORS:
        st.caption(t("history_all_vendor_hide"))
    else:
        export_df = model["export_df"]
        show_df = model["show_df"]
        cfg = {
            "日期顯示": st.column_config.TextColumn(t("date"), width="small"),
            "品項": st.column_config.TextColumn(width="medium"),
            "這次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
            "這次叫貨": st.column_config.NumberColumn(format="%.1f", width="small"),
            "日平均": st.column_config.NumberColumn(format="%.1f", width="small"),
        } if display_mode == DISPLAY_MODE_MOBILE else {
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
        st.download_button(t("download_csv"), export_df.to_csv(index=False).encode("utf-8-sig"), file_name=f"歷史叫貨紀錄_{sel_v}_{h_start}_{h_end}.csv", mime="text/csv", use_container_width=True, key="download_history_csv")
        render_report_dataframe(show_df, column_config=cfg)
    if st.button(f"⬅️ {t('back')}", use_container_width=True, key="back_hist_final"):
        st.session_state.step = "select_vendor"
        st.rerun()


def page_export():
    st.title(f"📤 {t('title_export')}")
    export_type = st.selectbox(t("label_export_type"), [t("export_today_purchase_detail"), t("export_analysis"), t("export_history")], key="export_type")
    selected_store_id, selected_store_name = _select_export_store("export_store_id")
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
    _download_csv_block(model["preview"], model["filename"])
    if st.button(f"⬅️ {t('back_to_menu')}", use_container_width=True, key="back_export_center"):
        st.session_state.step = "select_vendor"
        st.rerun()


def page_analysis():
    st.title(f"📊 {t('title_analysis')}")
    c_date1, c_date2 = st.columns(2)
    start = c_date1.date_input(t("start_date"), value=date.today() - timedelta(days=14), key="ana_start")
    end = c_date2.date_input(t("end_date"), value=date.today(), key="ana_end")
    shared_tables = load_report_shared_tables()
    preview_model = build_analysis_page_view_model(st.session_state.store_id, start, end, ALL_VENDORS, DISPLAY_MODE_MOBILE, shared_tables)
    if preview_model["hist_df"].empty and preview_model["purchase_filt"].empty:
        st.warning(t("analysis_no_records"))
        if st.button(f"⬅️ {t('back_to_menu')}", use_container_width=True, key="back_from_analysis_no_data"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return
    st.markdown("---")
    selected_vendor = st.selectbox(f"🏢 {t('select_vendor')}", options=preview_model["vendor_options"], index=0, key="ana_vendor_filter")
    display_mode = _display_mode_selector("analysis_display_mode")
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
            vendor_summary = format_mmdd_column(model["vendor_summary"].copy(), "日期")
            if display_mode == DISPLAY_MODE_MOBILE:
                vendor_summary["廠商"] = vendor_summary["廠商"].apply(lambda x: short_item_name(x, 10))
            st.download_button(t("download_csv"), model["vendor_summary"].to_csv(index=False).encode("utf-8-sig"), file_name=f"進銷存分析_全部廠商_{start}_{end}.csv", mime="text/csv", use_container_width=False, key="download_analysis_all_vendors")
            render_report_dataframe(vendor_summary, column_config={"日期": st.column_config.TextColumn(width="small"), "廠商": st.column_config.TextColumn(width="medium"), "進貨金額": st.column_config.NumberColumn(format="%.1f", width="small")})
        if st.button(f"⬅️ {t('back_to_menu')}", use_container_width=True, key="back_from_analysis_all"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return
    st.subheader(f"📦 {selected_vendor} {t('analysis_vendor_detail')}")
    if model["detail_df"].empty:
        st.info(t("current_vendor_no_data"))
    else:
        export_df = model["export_df"]
        show_df = model["show_df"]
        cfg = {"日期": st.column_config.TextColumn(width="small"), "品項": st.column_config.TextColumn(width="medium"), "這次庫存": st.column_config.NumberColumn(format="%.1f", width="small"), "這次叫貨": st.column_config.NumberColumn(format="%.1f", width="small"), "日平均": st.column_config.NumberColumn(format="%.1f", width="small")} if display_mode == DISPLAY_MODE_MOBILE else {"日期": st.column_config.TextColumn(width="small"), "品項": st.column_config.TextColumn(width="medium"), "上次庫存": st.column_config.NumberColumn(format="%.1f", width="small"), "期間進貨": st.column_config.NumberColumn(format="%.1f", width="small"), "庫存合計": st.column_config.NumberColumn(format="%.1f", width="small"), "這次庫存": st.column_config.NumberColumn(format="%.1f", width="small"), "期間消耗": st.column_config.NumberColumn(format="%.1f", width="small"), "這次叫貨": st.column_config.NumberColumn(format="%.1f", width="small"), "日平均": st.column_config.NumberColumn(format="%.1f", width="small")}
        st.download_button(t("download_csv"), export_df.to_csv(index=False).encode("utf-8-sig"), file_name=f"進銷存分析_{selected_vendor}_{start}_{end}.csv", mime="text/csv", use_container_width=False, key="download_analysis_single_vendor")
        render_report_dataframe(show_df, column_config=cfg)
    if st.button(f"⬅️ {t('back_to_menu')}", use_container_width=True, key="back_from_analysis_single"):
        st.session_state.step = "select_vendor"
        st.rerun()


def page_cost_debug():
    st.title(f"🧮 {t('title_cost_debug')}")
    shared_tables = load_report_shared_tables()
    selector = build_cost_debug_selector_data(shared_tables)
    if selector["items_df"].empty:
        st.warning(t("cost_debug_items_fail"))
        if st.button(f"⬅️ {t('back_to_menu')}", use_container_width=True, key="back_from_cost_debug_empty"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return
    work = selector["work"]
    selected_item_id = st.selectbox(t("select_item"), options=selector["item_options"], format_func=lambda x: work.loc[work["item_id"] == x, "item_label"].iloc[0], key="cost_debug_item_id")
    target_date = st.date_input(t("cost_debug_query_date"), value=st.session_state.record_date, key="cost_debug_date")
    model = build_cost_debug_view_model(shared_tables, selected_item_id, target_date)
    st.markdown("---")
    st.subheader(t("cost_debug_result"))
    st.write(f"**{t('item_name')}：** {work.loc[work['item_id'].astype(str).str.strip() == str(selected_item_id).strip(), 'item_label'].iloc[0].rsplit(' (', 1)[0]}")
    st.write(f"**{t('base_unit')}：** {model['base_unit'] or t('not_set')}")
    st.write(f"**{t('default_stock_unit')}：** {model['default_stock_unit'] or t('not_set')}")
    st.write(f"**{t('default_order_unit')}：** {model['default_order_unit'] or t('not_set')}")
    st.write(f"**{t('price')}：** {model['unit_price']}")
    st.write(f"**{t('price_unit')}：** {model['price_unit'] or t('not_set')}")
    st.write(f"**{t('effective_date')}：** {model['effective_date'] or t('not_set')}")
    st.write(f"**{t('base_unit_cost')}：** {model['base_unit_cost'] if model['base_unit_cost'] is not None else t('cannot_calculate')}")
    st.markdown("---")
    st.subheader(t("cost_debug_conversion"))
    conv_show = model["conv_show"]
    if conv_show.empty:
        st.caption(t("cost_debug_no_conversion"))
    else:
        render_report_dataframe(conv_show[[c for c in ["conversion_id", "from_unit", "to_unit", "ratio", "is_active"] if c in conv_show.columns]])
    if st.button(f"⬅️ {t('back_to_menu')}", use_container_width=True, key="back_from_cost_debug"):
        st.session_state.step = "select_vendor"
        st.rerun()
