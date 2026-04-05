from __future__ import annotations

import streamlit as st

from shared.core.app_runtime import get_settings_dict, save_system_appearance
from shared.utils.permissions import require_permission


def page_appearance_settings():
    st.title("🎨 系統外觀")

    if not require_permission("system.info.view"):
        return

    settings_map = get_settings_dict()

    current_system_name = settings_map.get("system_name", "營運管理系統")
    current_logo_url = settings_map.get("logo_url", "")

    st.caption("此頁只調整顯示相關設定，不修改營運邏輯。")

    system_name = st.text_input(
        "系統名稱",
        value=current_system_name,
        key="appearance_system_name",
    )

    logo_url = st.text_input(
        "Logo URL",
        value=current_logo_url,
        key="appearance_logo_url",
    )

    st.markdown("#### 預覽")
    preview_name = system_name.strip() or "營運管理系統"
    st.markdown(f"**目前預覽名稱：** {preview_name}")

    if logo_url.strip():
        try:
            st.image(logo_url.strip(), width=140)
        except Exception:
            st.warning("Logo 預覽失敗，請檢查 URL 是否正確。")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("💾 儲存外觀設定", width="stretch", key="save_appearance_settings"):
            try:
                save_system_appearance(system_name=system_name, logo_url=logo_url)
                st.success("外觀設定已儲存")
                st.rerun()
            except Exception as e:
                st.error(f"儲存失敗：{e}")

    with c2:
        if st.button("⬅️ 返回", width="stretch", key="back_from_appearance_settings"):
            st.session_state.step = "select_store"
            st.rerun()
