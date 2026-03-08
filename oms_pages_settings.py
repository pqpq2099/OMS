# ============================================================
# ORIVIA OMS - Settings Pages
# ============================================================

from __future__ import annotations

import streamlit as st


def _page_header(title: str, desc: str) -> None:
    st.title(title)
    st.caption(desc)
    st.divider()


def page_appearance() -> None:
    _page_header("外觀設定", "統一管理系統外觀顯示。")
    st.info("骨架版：先保留頁面位置。")
    st.write("之後會放：Logo、主題、顏色、側邊欄風格。")


def page_operation_rules() -> None:
    _page_header("營運規則", "管理與全系統營運邏輯有關的設定。")
    st.info("骨架版：先保留頁面位置。")
    st.write("之後會放：建議量倍率、分析天數、營運參數。")


def page_inventory_rules() -> None:
    _page_header("庫存規則", "管理 base unit、order unit、換算與庫存相關規則。")
    st.info("骨架版：先保留頁面位置。")
    st.write("之後會放：單位規則、換算規則、顯示規則。")
