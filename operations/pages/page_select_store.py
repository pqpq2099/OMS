from __future__ import annotations

import streamlit as st

from operations.logic import logic_order


def page_select_store():
    st.markdown(
        "<style>.block-container { padding-top: 4rem !important; }</style>",
        unsafe_allow_html=True,
    )
    st.title("🏠 選擇分店")

    view_model = logic_order.get_store_selection_view_model()
    stores_df = view_model["stores_df"]

    if view_model["error_message"]:
        st.error(view_model["error_message"])
        return

    if stores_df.empty:
        st.warning("目前沒有可選分店資料。")
        return

    for _, row in stores_df.iterrows():
        label = row["store_label"]
        store_id = str(row.get("store_id", "")).strip()
        if st.button(f"📍 {label}", key=f"store_{store_id}", use_container_width=True):
            st.session_state.store_id = store_id
            st.session_state.store_name = label
            st.session_state.vendor_id = ""
            st.session_state.vendor_name = ""
            st.session_state.step = "select_vendor"
            st.rerun()
