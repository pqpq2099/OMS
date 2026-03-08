from __future__ import annotations

from datetime import date

import streamlit as st

from oms_core import apply_global_style
from pages_order import (
    page_order_entry,
    page_select_store,
    page_select_vendor,
)
from pages_reports import (
    page_analysis,
    page_cost_debug,
    page_export,
    page_view_history,
)

from pages_admin import (
    page_admin_home,
    page_admin_vendors,
)
st.set_page_config(page_title="OMS 系統", layout="centered")


# ============================================================
# Session State
# ============================================================
def init_session():

    if "step" not in st.session_state:
        st.session_state.step = "select_store"

    if "record_date" not in st.session_state:
        st.session_state.record_date = date.today()

    if "store_id" not in st.session_state:
        st.session_state.store_id = ""

    if "store_name" not in st.session_state:
        st.session_state.store_name = ""

    if "vendor_id" not in st.session_state:
        st.session_state.vendor_id = ""

    if "vendor_name" not in st.session_state:
        st.session_state.vendor_name = ""


# ============================================================
# Sidebar
# ============================================================
def render_sidebar():

    with st.sidebar:

        st.title("ORIVIA OMS")

        st.markdown("---")

        # =========================
        # 分店
        # =========================
        st.markdown("### 📍 分店")

        if st.session_state.store_name:
            st.caption(f"目前分店：{st.session_state.store_name}")

        if st.button("選擇分店", use_container_width=True):
            st.session_state.step = "select_store"
            st.rerun()

        st.markdown("---")

        # =========================
        # 分析
        # =========================
        st.markdown("### 📊 分析")

        if st.button("進銷存分析", use_container_width=True):
            st.session_state.step = "analysis"
            st.rerun()

        if st.button("成本檢查", use_container_width=True):
            st.session_state.step = "cost_debug"
            st.rerun()

        if st.button("歷史紀錄", use_container_width=True):
            st.session_state.step = "view_history"
            st.rerun()

        st.markdown("---")

        st.caption("OMS Schema v1")


# ============================================================
# Router
# ============================================================
def router():

    step = st.session_state.step

    if step == "select_store":
        page_select_store()

    elif step == "select_vendor":
        page_select_vendor()

    elif step == "order_entry":
        page_order_entry()

    elif step == "view_history":
        page_view_history()

    elif step == "export":
        page_export()

    elif step == "analysis":
        page_analysis()

    elif step == "cost_debug":
        page_cost_debug()

    elif step == "admin_home":
    page_admin_home()

    elif step == "admin_vendors":
    page_admin_vendors()
    
    else:
        page_select_store()
        
    st.markdown("---")
    
    st.markdown("### ⚙ 系統管理")
    
    if st.button("系統管理", use_container_width=True):
        st.session_state.step = "admin_home"
        st.rerun()

# ============================================================
# Main
# ============================================================
def main():

    apply_global_style()

    init_session()

    render_sidebar()

    router()


if __name__ == "__main__":
    main()

