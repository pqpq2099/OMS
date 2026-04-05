from __future__ import annotations

import streamlit as st

import shared.core.app_runtime as app_runtime
from shared.utils.permissions import require_permission
from system.logic import apply_login_enabled_toggle


def page_system_tools():
    st.title("🧰 系統工具")

    if not require_permission("system.manage"):
        return

    if not app_runtime.require_locked_system_page("系統工具"):
        return

    st.info("這一頁保留給 Owner 放臨時測試、偵錯工具與未來的小型系統輔助功能。")

    st.markdown("### 登入畫面開關")
    toggle_state = app_runtime.get_login_toggle_state()
    bypass_mode = bool(st.session_state.get("login_bypass_mode", False))

    if toggle_state["status_level"] == "success":
        st.success(toggle_state["status_text"])
    else:
        st.warning(toggle_state["status_text"])

    toggle_label = toggle_state["toggle_label"]
    next_value = toggle_state["next"]
    toggle_help = toggle_state["toggle_help"]

    st.caption(toggle_help)

    if st.button(toggle_label, width="stretch", type="primary", key="toggle_login_enabled"):
        try:
            apply_login_enabled_toggle(next_value)
            st.success("登入畫面設定已更新。")
            st.rerun()
        except Exception as e:
            st.error(f"切換失敗：{e}")

    st.markdown("---")

    if st.button("♻️ 重新整理快取", width="stretch"):
        app_runtime.refresh_runtime_sheet_cache()
        st.success("已清除 read_table 快取。")

    st.markdown("### 目前狀態")
    st.write(f"目前角色：{st.session_state.get('role', '')}")
    st.write(f"目前 step：{st.session_state.get('step', '')}")
    st.write(f"目前分店：{st.session_state.get('store_name', '')}")
    st.write(f"目前廠商：{st.session_state.get('vendor_name', '')}")
    st.write(f"免登入模式：{'是' if bypass_mode else '否'}")

    if st.button("⬅️ 返回", width="stretch", key="back_from_system_tools"):
        st.session_state.step = "select_store"
        st.rerun()
