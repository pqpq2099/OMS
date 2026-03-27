from __future__ import annotations

from datetime import date

import streamlit as st

from operations.logic import logic_stock_record
from shared.core.navigation import goto
from shared.utils.utils_format import _fmt_qty_with_unit, unit_label
from shared.services import service_order_core


def page_daily_stock_order_record():
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem !important;
            padding-left: 0.35rem !important;
            padding-right: 0.35rem !important;
        }

        [data-testid='stHorizontalBlock'] {
            display: flex !important;
            flex-flow: row nowrap !important;
            align-items: flex-start !important;
            gap: 0.35rem !important;
        }

        div[data-testid='stHorizontalBlock'] > div:nth-child(1) {
            flex: 1 1 auto !important;
            min-width: 0px !important;
        }

        div[data-testid='stHorizontalBlock'] > div:nth-child(2),
        div[data-testid='stHorizontalBlock'] > div:nth-child(3) {
            flex: 0 0 84px !important;
            min-width: 84px !important;
            max-width: 84px !important;
        }

        div[data-testid='stNumberInput'] label {
            display: none !important;
        }

        div[data-testid="stNumberInput"] input {
            text-align: center !important;
            padding-left: 0.4rem !important;
            padding-right: 0.4rem !important;
        }

        .order-divider {
            margin: 10px 0 14px 0;
            border-top: 1px solid rgba(128,128,128,0.25);
        }

        .order-meta {
            font-size: 0.82rem;
            color: rgba(170, 178, 195, 0.9);
            margin-top: -0.2rem;
            margin-bottom: 0.25rem;
        }

        .order-unit-label {
            display: flex;
            align-items: flex-end;
            justify-content: center;
            height: 34px;
            font-size: 1rem;
            font-weight: 500;
            opacity: 0.9;
            margin-top: 3px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("📋 當日庫存叫貨紀錄")

    store_id = service_order_core.norm(st.session_state.get("store_id", ""))
    store_name = st.session_state.get("store_name", "")

    if not store_id:
        st.warning("請先選擇分店。")
        if st.button("⬅️ 返回分店列表", use_container_width=True):
            goto("select_store")
        return

    selected_date = st.date_input(
        "📅 日期",
        value=st.session_state.get("record_date", date.today()),
        key="daily_record_date",
    )

    base_model = logic_stock_record.build_daily_stock_order_record_view_model(
        store_id=store_id,
        store_name=store_name,
        selected_date=selected_date,
    )
    if base_model.get("status") != "ok":
        status = base_model.get("status")
        message = base_model.get("message", "讀取失敗")
        if status == "warning":
            st.warning(message)
        else:
            st.info(message)
        return

    vendor_options = base_model.get("vendor_options", [])
    vendor_labels = [row.get("vendor_label", "") for row in vendor_options]
    default_vendor_id = service_order_core.norm(st.session_state.get("vendor_id", ""))
    vendor_id_to_label = {row.get("vendor_id", ""): row.get("vendor_label", "") for row in vendor_options}
    vendor_label_to_id = {row.get("vendor_label", ""): row.get("vendor_id", "") for row in vendor_options}

    default_index = 0
    if default_vendor_id and default_vendor_id in vendor_id_to_label:
        default_label = vendor_id_to_label[default_vendor_id]
        if default_label in vendor_labels:
            default_index = vendor_labels.index(default_label)

    selected_vendor_label = st.selectbox(
        "🏢 選擇廠商",
        options=vendor_labels,
        index=default_index,
        key="daily_record_vendor",
    )
    vendor_id = vendor_label_to_id.get(selected_vendor_label, "")

    detail_model = logic_stock_record.build_vendor_daily_record_rows(
        page_tables=base_model["page_tables"],
        items_df=base_model["items_df"],
        po_df=base_model["po_df"],
        pol_df=base_model["pol_df"],
        stocktakes_df=base_model["stocktakes_df"],
        stocktake_lines_df=base_model["stocktake_lines_df"],
        latest_metrics_map=base_model["latest_metrics_map"],
        store_id=store_id,
        vendor_id=vendor_id,
        selected_date=selected_date,
    )
    if detail_model.get("status") != "ok":
        st.info(detail_model.get("message", "目前沒有資料"))
        if detail_model.get("message") == "這一天目前沒有找到庫存 / 叫貨紀錄。":
            if st.button("⬅️ 返回廠商選單", use_container_width=True):
                goto("select_vendor")
        return

    st.caption(f"{store_name}｜{selected_vendor_label}｜最近一筆紀錄")

    st.markdown("<div class='order-divider'></div>", unsafe_allow_html=True)

    h1, h2, h3 = st.columns([6, 1, 1])
    h1.write("**品項名稱（建議量=日均×1.5）**")
    h2.write("<div style='text-align:center;'><b>庫</b></div>", unsafe_allow_html=True)
    h3.write("<div style='text-align:center;'><b>進</b></div>", unsafe_allow_html=True)

    for row in detail_model.get("rows", []):
        item_id = row.get("item_id", "")
        c1, c2, c3 = st.columns([6, 1, 1])

        with c1:
            st.write(f"<b>{row.get('item_name', '')}</b>", unsafe_allow_html=True)
            tail = f"　{row.get('status_hint', '')}" if row.get("status_hint") else ""
            st.markdown(
                f"<div class='order-meta'>總庫存：{_fmt_qty_with_unit(row.get('stock_display', 0), row.get('stock_unit_default', ''))}　建議量：{_fmt_qty_with_unit(row.get('suggest_display', 0), row.get('stock_unit_default', ''))}{tail}</div>",
                unsafe_allow_html=True,
            )

        with c2:
            st.number_input(
                "庫",
                min_value=0.0,
                step=0.1,
                format="%g",
                value=float(row.get("stock_qty", 0.0)),
                key=f"daily_record_stock_{item_id}",
                label_visibility="collapsed",
                disabled=True,
            )
            st.markdown(
                f"<div class='order-unit-label'>{unit_label(row.get('stock_unit', ''))}</div>",
                unsafe_allow_html=True,
            )

        with c3:
            st.number_input(
                "進",
                min_value=0.0,
                step=0.1,
                format="%g",
                value=float(row.get("order_qty", 0.0)),
                key=f"daily_record_order_{item_id}",
                label_visibility="collapsed",
                disabled=True,
            )
            st.selectbox(
                "進貨單位",
                options=[row.get("order_unit", "") or "-"],
                index=0,
                key=f"daily_record_unit_{item_id}",
                label_visibility="collapsed",
                disabled=True,
                format_func=unit_label,
            )

    st.markdown("<div class='order-divider'></div>", unsafe_allow_html=True)

    if st.button("⬅️ 返回廠商選單", use_container_width=True):
        st.session_state.step = "select_vendor"
        st.rerun()
