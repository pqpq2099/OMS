# ============================================================
# ORIVIA OMS
# Main Router
# ============================================================

from __future__ import annotations

import streamlit as st


# ============================================================
# Page Config
# ============================================================

st.set_page_config(
    page_title="ORIVIA OMS",
    page_icon="📦",
    layout="wide",
)


# ============================================================
# Import Pages
# ============================================================

from oms_pages_store import page_order_entry
from oms_pages_analysis import (
    page_inventory_analysis,
    page_cost_analysis,
    page_purchase_report,
)
from oms_pages_admin import page_admin_panel


# ============================================================
# Session
# ============================================================

if "page" not in st.session_state:
    st.session_state.page = "order"


# ============================================================
# Sidebar
# ============================================================

def render_sidebar():

    with st.sidebar:

        st.title("ORIVIA OMS")

        st.markdown("---")

        st.subheader("門市營運")

        if st.button("叫貨 / 庫存"):
            st.session_state.page = "order"

        st.markdown("---")

        st.subheader("分析")

        if st.button("進銷存分析"):
            st.session_state.page = "inventory_analysis"

        if st.button("成本分析"):
            st.session_state.page = "cost_analysis"

        if st.button("進貨報表"):
            st.session_state.page = "purchase_report"

        st.markdown("---")

        st.subheader("系統")

        if st.button("系統管理"):
            st.session_state.page = "admin"


# ============================================================
# Router
# ============================================================

def router():

    page = st.session_state.page

    if page == "order":
        page_order_entry()

    elif page == "inventory_analysis":
        page_inventory_analysis()

    elif page == "cost_analysis":
        page_cost_analysis()

    elif page == "purchase_report":
        page_purchase_report()

    elif page == "admin":
        page_admin_panel()


# ============================================================
# Main
# ============================================================

def main
