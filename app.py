# ============================================================
# ORIVIA OMS
# app.py
# 穩定 Router 版（避免 import 名稱不一致直接炸掉）
# ============================================================

from __future__ import annotations

import streamlit as st

import oms_pages_store as store_pages
import oms_pages_analysis as analysis_pages
import oms_pages_admin as admin_pages


# ============================================================
# Page Config
# ============================================================

st.set_page_config(
    page_title="ORIVIA OMS",
    page_icon="📦",
    layout="wide",
)


# ============================================================
# Session State
# ============================================================

if "page" not in st.session_state:
    st.session_state.page = "order"


# ============================================================
# Safe Resolver
# ============================================================

def _resolve_page(module, candidates: list[str]):
    for name in candidates:
        fn = getattr(module, name, None)
        if callable(fn):
            return fn
    return None


def _render_missing_page(title: str, module_name: str, candidates: list[str]) -> None:
    st.title(title)
    st.error(f"找不到可用頁面函式：{module_name}")
    st.caption("請確認下列其中一個函式名稱是否存在：")
    for name in candidates:
        st.code(name)


# ============================================================
# Sidebar
# ============================================================

def render_sidebar() -> None:
    with st.sidebar:
        st.title("ORIVIA OMS")

        st.markdown("---")
        st.subheader("門市營運")

        if st.button("叫貨 / 庫存", use_container_width=True):
            st.session_state.page = "order"

        if st.button("叫貨紀錄", use_container_width=True):
            st.session_state.page = "order_history"

        if st.button("盤點歷史", use_container_width=True):
            st.session_state.page = "stocktake_history"

        st.markdown("---")
        st.subheader("數據分析")

        if st.button("進銷存分析", use_container_width=True):
            st.session_state.page = "inventory_analysis"

        if st.button("成本分析", use_container_width=True):
            st.session_state.page = "cost_analysis"

        if st.button("進貨報表", use_container_width=True):
            st.session_state.page = "purchase_report"

        st.markdown("---")
        st.subheader("系統管理")

        if st.button("系統管理", use_container_width=True):
            st.session_state.page = "admin"


# ============================================================
# Router
# ============================================================

def router() -> None:
    page = st.session_state.page

    if page == "order":
        fn = _resolve_page(
            store_pages,
            ["page_order_entry", "page_order"],
        )
        if fn:
            fn()
        else:
            _render_missing_page(
                "叫貨 / 庫存",
                "oms_pages_store.py",
                ["page_order_entry", "page_order"],
            )

    elif page == "order_history":
        fn = _resolve_page(
            store_pages,
            ["page_order_history"],
        )
        if fn:
            fn()
        else:
            _render_missing_page(
                "叫貨紀錄",
                "oms_pages_store.py",
                ["page_order_history"],
            )

    elif page == "stocktake_history":
        fn = _resolve_page(
            store_pages,
            ["page_stocktake_history"],
        )
        if fn:
            fn()
        else:
            _render_missing_page(
                "盤點歷史",
                "oms_pages_store.py",
                ["page_stocktake_history"],
            )

    elif page == "inventory_analysis":
        fn = _resolve_page(
            analysis_pages,
            ["page_inventory_analysis", "page_analysis_inventory", "page_analysis"],
        )
        if fn:
            fn()
        else:
            _render_missing_page(
                "進銷存分析",
                "oms_pages_analysis.py",
                ["page_inventory_analysis", "page_analysis_inventory", "page_analysis"],
            )

    elif page == "cost_analysis":
        fn = _resolve_page(
            analysis_pages,
            ["page_cost_analysis", "page_analysis_cost", "page_cost"],
        )
        if fn:
            fn()
        else:
            _render_missing_page(
                "成本分析",
                "oms_pages_analysis.py",
                ["page_cost_analysis", "page_analysis_cost", "page_cost"],
            )

    elif page == "purchase_report":
        fn = _resolve_page(
            analysis_pages,
            ["page_purchase_report", "page_report_purchase"],
        )
        if fn:
            fn()
        else:
            _render_missing_page(
                "進貨報表",
                "oms_pages_analysis.py",
                ["page_purchase_report", "page_report_purchase"],
            )

    elif page == "admin":
        fn = _resolve_page(
            admin_pages,
            ["page_admin_panel", "page_admin", "page_admin_home"],
        )
        if fn:
            fn()
        else:
            _render_missing_page(
                "系統管理",
                "oms_pages_admin.py",
                ["page_admin_panel", "page_admin", "page_admin_home"],
            )

    else:
        st.session_state.page = "order"
        st.rerun()


# ============================================================
# Main
# ============================================================

def main() -> None:
    render_sidebar()
    router()


if __name__ == "__main__":
    main()
