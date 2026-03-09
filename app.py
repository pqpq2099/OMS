# ============================================================
# ORIVIA OMS
# Main App Router
# ============================================================

from __future__ import annotations

import streamlit as st


# ============================================================
# Page Config
# ============================================================

st.set_page_config(
    page_title="ORIVIA OMS",
    page_icon="📦",
    layout="wide"
)


# ============================================================
# Import Pages
# ============================================================

from oms_pages_store import (
    page_order_entry,
    page_order_history,
    page_stocktake_history,
)

from oms_pages_analysis import (
    page_analysis_inventory,
    page_analysis_cost,
)

from oms_pages_admin import (
    page_admin_vendors,
    page_admin_items,
)


# ============================================================
# Session State
# ============================================================

if "page" not in st.session_state:
    st.session_state.page = "order"


# ============================================================
# Sidebar
# ============================================================

def render_sidebar():

    with st.sidebar:

        st.title("📦 ORIVIA OMS")

        st.markdown("---")

        st.subheader("Operations")

        if st.button("叫貨 / 庫存"):
            st.session_state.page = "order"

        if st.button("叫貨紀錄"):
            st.session_state.page = "order_history"

        if st.button("盤點歷史"):
            st.session_state.page = "stocktake_history"

        st.markdown("---")

        st.subheader("Analysis")

        if st.button("進銷存分析"):
            st.session_state.page = "analysis_inventory"

        if st.button("成本分析"):
            st.session_state.page = "analysis_cost"

        st.markdown("---")

        st.subheader("Admin")

        if st.button("廠商管理"):
            st.session_state.page = "admin_vendors"

        if st.button("品項管理"):
            st.session_state.page = "admin_items"


# ============================================================
# Router
# ============================================================

def router():

    page = st.session_state.page

    if page == "order":
        page_order_entry()

    elif page == "order_history":
        page_order_history()

    elif page == "stocktake_history":
        page_stocktake_history()

    elif page == "analysis_inventory":
        page_analysis_inventory()

    elif page == "analysis_cost":
        page_analysis_cost()

    elif page == "admin_vendors":
        page_admin_vendors()

    elif page == "admin_items":
        page_admin_items()

    else:
        st.session_state.page = "order"
        page_order_entry()


# ============================================================
# Main
# ============================================================

def main():

    render_sidebar()

    router()


if __name__ == "__main__":
    main()
