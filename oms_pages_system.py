# ============================================================
# ORIVIA OMS - System Pages
# ============================================================

from __future__ import annotations

import streamlit as st


def page_system_info() -> None:
    st.title("系統資訊")
    st.caption("查看系統版本、資料庫狀態與後續系統資訊。")
    st.divider()

    st.info("骨架版：先保留頁面位置。")

    col1, col2 = st.columns(2)
    col1.metric("系統版本", "Skeleton v1")
    col2.metric("資料庫", "Google Sheets")

    st.subheader("預計內容")
    st.write("之後會放：DB版本、最後更新時間、audit log 摘要、系統狀態。")
