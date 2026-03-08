# ============================================================
# ORIVIA OMS - Analysis Pages
# ============================================================

from __future__ import annotations

import streamlit as st


def _page_header(title: str, desc: str) -> None:
    st.title(title)
    st.caption(desc)
    st.divider()


def page_inventory_analysis() -> None:
    _page_header("進銷存分析", "查看期間消耗、趨勢變化與品項排行。")

    st.info("骨架版：此頁先保留位置，後續再接 KPI / 趨勢圖 / Top20。")

    c1, c2, c3 = st.columns(3)
    c1.metric("期間消耗", "0")
    c2.metric("活用品項", "0")
    c3.metric("分析區間", "-")

    st.subheader("預計內容")
    st.write("之後會放：篩選條件、KPI卡片、趨勢圖、Top20排行、明細表。")


def page_cost_analysis() -> None:
    _page_header("成本分析", "查看期間成本、庫存殘值與 base unit 成本計算結果。")

    st.info("骨架版：此頁先保留位置，後續再接 prices / unit_conversions / stocktakes。")

    c1, c2 = st.columns(2)
    c1.metric("期間成本", "0")
    c2.metric("庫存殘值", "0")

    st.subheader("固定邏輯")
    st.write("base_qty × base_unit_cost")

    st.subheader("預計內容")
    st.write("之後會放：成本摘要、品項成本表、分店成本比較。")


def page_purchase_report() -> None:
    _page_header("進貨報表", "查看期間進貨金額、廠商統計與品項採購彙總。")

    st.info("骨架版：此頁先保留位置，後續再接 purchase_orders / purchase_order_lines。")

    st.subheader("預計內容")
    st.write("之後會放：廠商彙總、品項彙總、明細表、日期篩選。")
