# ============================================================
# ORIVIA OMS - Admin Pages
# ============================================================

from __future__ import annotations

import streamlit as st


def _page_header(title: str, desc: str) -> None:
    st.title(title)
    st.caption(desc)
    st.divider()


def page_vendors() -> None:
    _page_header("廠商管理", "管理 vendors 主資料。")
    st.info("骨架版：先保留頁面位置。")
    st.write("之後會放：廠商清單、新增廠商、啟用 / 停用。")


def page_items() -> None:
    _page_header("品項管理", "管理 items 主資料與 ingredient / product 分類。")
    st.info("骨架版：先保留頁面位置。")
    st.write("之後會放：品項清單、品項新增、預設廠商、預設單位。")


def page_stores() -> None:
    _page_header("分店管理", "管理 stores 主資料。")
    st.info("骨架版：先保留頁面位置。")
    st.write("之後會放：分店清單、新增分店、啟用 / 停用。")


def page_brands() -> None:
    _page_header("品牌管理", "管理 brands 主資料，保留多品牌延伸能力。")
    st.info("骨架版：先保留頁面位置。")
    st.write("之後會放：品牌清單、新增品牌、品牌狀態。")


def page_users() -> None:
    _page_header("帳號權限", "管理 users / roles 與系統權限層級。")
    st.info("骨架版：先保留頁面位置。")
    st.write("之後會放：帳號列表、角色設定、分店權限綁定。")
