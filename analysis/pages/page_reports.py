from __future__ import annotations

from datetime import date

import streamlit as st

from shared.services.service_reports import render_report_dataframe
from analysis.logic.report_query import load_report_shared_tables
from analysis.logic.report_view_model import (
    ALL_VENDORS,
    build_cost_debug_display_model,
    build_stock_order_compare_view_model,
)
from ui_text import t

from analysis.pages.page_export import page_export_report
from analysis.pages.page_inventory_analysis import page_inventory_analysis
from analysis.pages.page_order_history import page_order_history
from analysis.pages.shared import download_csv_block
from shared.utils.permissions import require_permission


def page_stock_order_compare():
    if not require_permission("analysis.dashboard.view"):
        return
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
    download_csv_block(preview, f"stock_order_compare_{store_id}_{selected_date}.csv")
    if st.button(f"⬅️ {t('back_to_function_menu')}", use_container_width=True, key="back_from_stock_order_compare"):
        st.session_state.step = "select_vendor"
        st.rerun()


def page_view_history():
    if not require_permission("analysis.dashboard.view"):
        return
    page_order_history()


def page_export():
    if not require_permission("analysis.export.execute"):
        return
    page_export_report()


def page_analysis():
    if not require_permission("analysis.dashboard.view"):
        return
    page_inventory_analysis()


def page_cost_debug():
    st.title(f"🧮 {t('title_cost_debug')}")
    shared_tables = load_report_shared_tables()
    preloaded_debug = build_cost_debug_display_model(shared_tables, "", st.session_state.record_date)
    selector = preloaded_debug["selector"]
    if selector["items_df"].empty:
        st.warning(t("cost_debug_items_fail"))
        if st.button(f"⬅️ {t('back_to_menu')}", use_container_width=True, key="back_from_cost_debug_empty"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return
    selected_item_id = st.selectbox(
        t("select_item"),
        options=selector["item_options"],
        format_func=lambda x: selector["item_label_map"].get(str(x).strip(), str(x)),
        key="cost_debug_item_id",
    )
    target_date = st.date_input(t("cost_debug_query_date"), value=st.session_state.record_date, key="cost_debug_date")
    debug_model = build_cost_debug_display_model(shared_tables, selected_item_id, target_date)
    model = debug_model["model"]
    st.markdown("---")
    st.subheader(t("cost_debug_result"))
    st.write(f"**{t('item_name')}：** {debug_model['item_name']}")
    st.write(f"**{t('base_unit')}：** {model['base_unit'] or t('not_set')}")
    st.write(f"**{t('default_stock_unit')}：** {model['default_stock_unit'] or t('not_set')}")
    st.write(f"**{t('default_order_unit')}：** {model['default_order_unit'] or t('not_set')}")
    st.write(f"**{t('price')}：** {model['unit_price']}")
    st.write(f"**{t('price_unit')}：** {model['price_unit'] or t('not_set')}")
    st.write(f"**{t('effective_date')}：** {model['effective_date'] or t('not_set')}")
    st.write(f"**{t('base_unit_cost')}：** {model['base_unit_cost'] if model['base_unit_cost'] is not None else t('cannot_calculate')}")
    st.markdown("---")
    st.subheader(t("cost_debug_conversion"))
    conv_show = debug_model["conv_display"]
    if conv_show.empty:
        st.caption(t("cost_debug_no_conversion"))
    else:
        render_report_dataframe(conv_show)
    if st.button(f"⬅️ {t('back_to_menu')}", use_container_width=True, key="back_from_cost_debug"):
        st.session_state.step = "select_vendor"
        st.rerun()
