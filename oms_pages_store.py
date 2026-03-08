# ============================================================
# ORIVIA OMS - Store Pages
# ============================================================

from __future__ import annotations

import streamlit as st


def _page_header(title: str, desc: str) -> None:
    st.title(title)
    st.caption(desc)
    st.divider()


def page_order_entry() -> None:
    _page_header("叫貨 / 庫存", "門市日常操作入口：之後放庫存輸入、進貨輸入、建議量。")

    st.info("骨架版：此頁先確認 Sidebar / Router / Page 結構正常。")

    col1, col2, col3 = st.columns(3)
    col1.metric("品項數", "0")
    col2.metric("今日進貨筆數", "0")
    col3.metric("待補功能", "建議量 / 寫入")

    st.subheader("頁面用途")
    st.write("之後會放：分店選擇、廠商選擇、品項清單、庫存欄位、進貨欄位、進貨單位。")


def page_order_history() -> None:
    _page_header("叫貨紀錄", "查看歷史叫貨資料、廠商進貨內容與金額。")

    st.info("骨架版：此頁先保留位置，後續再接 purchase_orders / purchase_order_lines。")

    st.subheader("預計內容")
    st.write("之後會放：日期篩選、分店篩選、廠商篩選、進貨明細表。")


def page_stocktake_history() -> None:
    _page_header("盤點歷史", "查看每次盤點前後的庫存變化與期間消耗。")

    st.info("骨架版：此頁先保留位置，後續再接 stocktakes / stocktake_lines。")

    st.subheader("固定邏輯")
    st.write("上次庫存 + 期間進貨 - 這次庫存 = 期間消耗")

    st.subheader("預計欄位")
    st.write("日期 / 品項 / 上次庫存 / 期間進貨 / 庫存合計 / 這次庫存 / 期間消耗 / 日平均")
