from __future__ import annotations

from datetime import date

import streamlit as st

from oms_core import apply_global_style

from pages_order import (
    page_order_entry,
    page_select_store,
    page_select_vendor,
)

from pages_stocktake import page_stocktake

from pages_reports import (
    page_analysis,
    page_cost_debug,
    page_export,
    page_view_history,
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
        st.markdown("## ORIVIA OMS")
        st.caption("OMS Schema v1")

        if st.session_state.store_name:
            st.write(f"**分店：** {st.session_state.store_name}")
        if st.session_state.vendor_name:
            st.write(f"**廠商：** {st.session_state.vendor_name}")

        st.markdown("---")

        if st.button("🏠 選擇分店", use_container_width=True, key="sb_select_store"):
            st.session_state.step = "select_store"
            st.rerun()

        if st.session_state.store_id:
            if st.button("🏢 分店功能選單", use_container_width=True, key="sb_select_vendor"):
                st.session_state.step = "select_vendor"
                st.rerun()

        if st.session_state.vendor_id:
            if st.button("📝 叫貨 / 庫存", use_container_width=True, key="sb_order_entry"):
                st.session_state.step = "order_entry"
                st.rerun()
            if st.button("📦 點貨 / 叫貨測試頁", use_container_width=True, key="sb_stocktake"):
                st.session_state.step = "stocktake"
                st.rerun()
        if st.session_state.store_id:
            if st.button("📋 今日進貨明細", use_container_width=True, key="sb_export"):
                st.session_state.step = "export"
                st.rerun()

            if st.button("📈 期間進銷存分析", use_container_width=True, key="sb_analysis"):
                st.session_state.step = "analysis"
                st.rerun()

            if st.button("🧮 成本檢查", use_container_width=True, key="sb_cost_debug"):
                st.session_state.step = "cost_debug"
                st.rerun()

            if st.button("📜 歷史紀錄", use_container_width=True, key="sb_view_history"):
                st.session_state.step = "view_history"
                st.rerun()


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
    else:
        page_select_store()


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


