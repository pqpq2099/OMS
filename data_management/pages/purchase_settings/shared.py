# ============================================================
# ORIVIA OMS
# 檔案：pages/purchase_settings/shared.py
# 說明：採購設定頁面共用 UI helper
# ============================================================

from __future__ import annotations

import streamlit as st

__all__ = ["st", "_render_section_title"]


def _render_section_title(title: str, help_text: str = ""):
    st.subheader(title)
    if help_text:
        st.caption(help_text)
