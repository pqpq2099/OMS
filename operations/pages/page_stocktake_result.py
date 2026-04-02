# ============================================================
# ORIVIA OMS
# 檔案：operations/pages/page_stocktake_result.py
# 說明：盤點送出結果頁
# 功能：顯示本次盤點與叫貨單建立結果，提供三個導頁選項。
# 入口：由 page_stocktake 送出成功後跳轉，不可直接從選單進入。
# ============================================================

"""
頁面模組：盤點送出結果頁。
page_stocktake 成功送出後自動跳轉此頁。
結果資料由 session_state 傳入，不再查詢 DB。
"""

from __future__ import annotations

import streamlit as st

from shared.core.navigation import goto


# ----------------------------------------------------------
# session_state 鍵值（與 page_stocktake.py 共用）
# ----------------------------------------------------------
_STK_IDS_KEY = "_stk_result_stocktake_ids"
_PO_IDS_KEY = "_stk_result_po_ids"


# ----------------------------------------------------------
# [S1] 盤點結果主畫面
# ----------------------------------------------------------
def render_stocktake_result() -> None:
    """盤點送出結果主畫面。"""
    st.title("✅ 盤點送出完成")

    stocktake_ids: list = st.session_state.get(_STK_IDS_KEY, [])
    po_ids: list = st.session_state.get(_PO_IDS_KEY, [])

    # 防呆：若 session_state 無資料（使用者直接進入此頁）
    if not stocktake_ids and not po_ids:
        st.info("沒有可顯示的盤點結果，請先完成盤點送出。")
        if st.button("⬅️ 返回主選單", use_container_width=True):
            goto("select_vendor")
        return

    stk_count = len(stocktake_ids)
    po_count = len(po_ids)

    # ── 盤點結果 ──────────────────────────────────────────
    st.markdown(f"**本次建立盤點：{stk_count} 筆**")
    for sid in stocktake_ids:
        st.markdown(f"- `{sid}`")

    st.divider()

    # ── 叫貨單結果 ────────────────────────────────────────
    if po_ids:
        st.markdown(f"**本次建立叫貨單：{po_count} 筆**")
        for pid in po_ids:
            st.markdown(f"- `{pid}`")
    else:
        st.markdown("**本次叫貨單**")
        st.info("本次無叫貨單（所有品項叫貨量為 0）")

    st.divider()

    # ── 導頁按鈕 ─────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅️ 返回主選單", use_container_width=True, key="sr_back"):
            goto("select_vendor")
    with col2:
        if st.button("📋 叫貨單管理", use_container_width=True, key="sr_po"):
            goto("purchase_orders")
    with col3:
        if st.button("🕐 盤點歷史", use_container_width=True, key="sr_history"):
            goto("stocktake_history")


# ----------------------------------------------------------
# [S2] 頁面入口（給 router 用）
# ----------------------------------------------------------
def page_stocktake_result() -> None:
    """盤點送出結果頁入口。"""
    render_stocktake_result()
