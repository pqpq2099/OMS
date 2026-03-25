from __future__ import annotations

import pandas as pd
import streamlit as st

from shared.core.app_runtime import get_settings_dict


def page_system_info():
    st.title("ℹ️ 系統資訊")

    if st.session_state.role not in ["owner", "admin"]:
        st.error("你沒有權限進入此頁。")
        return

    settings_map = get_settings_dict()

    display_rows = [
        ("系統名稱", settings_map.get("system_name", "營運管理系統")),
        ("幣別", settings_map.get("currency", "")),
        ("時區", settings_map.get("timezone", "")),
        ("建議叫貨天數", settings_map.get("default_suggestion_days", "")),
        ("歷史天數", settings_map.get("history_days", "")),
        ("Logo URL", settings_map.get("logo_url", "")),
    ]

    st.caption("此頁以查看系統目前設定為主，不直接修改營運邏輯參數。")
    info_df = pd.DataFrame(display_rows, columns=["項目", "目前值"])
    st.dataframe(info_df, width="stretch", hide_index=True)

    if st.button("⬅️ 返回", width="stretch", key="back_from_system_info"):
        st.session_state.step = "select_store"
        st.rerun()
