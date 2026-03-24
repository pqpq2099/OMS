from __future__ import annotations

from datetime import date

import streamlit as st

from operations.logic import logic_order


def page_select_vendor():
    st.markdown(
        "<style>.block-container { padding-top: 4rem !important; }</style>",
        unsafe_allow_html=True,
    )
    st.title(f"🏢 {st.session_state.store_name}")

    selected_record_date = st.date_input(
        "📅 作業日期",
        value=st.session_state.get("record_date", date.today()),
        key="select_vendor_record_date",
    )
    st.session_state.record_date = selected_record_date

    view_model = logic_order.get_vendor_selection_view_model(
        record_date=selected_record_date,
        store_id=st.session_state.get("store_id", ""),
    )
    vendors_df = view_model["vendors_df"]
    items_df = view_model["items_df"]
    vendors = view_model["vendors"]

    if vendors_df.empty or items_df.empty:
        st.warning("目前缺少廠商或品項資料。")
        return

    if vendors.empty:
        st.warning("目前沒有可選廠商。")
        return

    for i in range(0, len(vendors), 2):
        cols = st.columns(2)

        left = vendors.iloc[i]
        with cols[0]:
            if st.button(
                f"📦 {left['vendor_label']}",
                key=f"vendor_{left.get('vendor_id', '')}",
                use_container_width=True,
            ):
                st.session_state.vendor_id = str(left.get("vendor_id", "")).strip()
                st.session_state.vendor_name = left["vendor_label"]
                st.session_state.step = "order_entry"
                st.rerun()

        if i + 1 < len(vendors):
            right = vendors.iloc[i + 1]
            with cols[1]:
                if st.button(
                    f"📦 {right['vendor_label']}",
                    key=f"vendor_{right.get('vendor_id', '')}",
                    use_container_width=True,
                ):
                    st.session_state.vendor_id = str(right.get("vendor_id", "")).strip()
                    st.session_state.vendor_name = right["vendor_label"]
                    st.session_state.step = "order_entry"
                    st.rerun()

    st.write("<b>📊 報表與分析中心</b>", unsafe_allow_html=True)

    if st.button("📄 產生今日進貨明細", type="primary", use_container_width=True):
        st.session_state.step = "order_message_detail"
        st.rerun()

    if st.button("⬅️ 返回分店列表", use_container_width=True):
        st.session_state.step = "select_store"
        st.rerun()
