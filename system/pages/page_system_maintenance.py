from __future__ import annotations

import streamlit as st

import shared.core.app_runtime as app_runtime


def page_system_maintenance():
    st.title("🛠️ 系統維護")

    if st.session_state.role != "owner":
        st.error("你沒有權限進入此頁。")
        return

    if not app_runtime.require_locked_system_page("系統維護"):
        return

    st.markdown("### 初始化營運資料")
    st.warning("此功能會清空庫存、叫貨與交易資料，並將對應序號重設回 1。主資料不會刪除。")

    target_tables, target_sequence_keys = app_runtime.get_system_reset_targets()

    with st.expander("查看本次初始化範圍", expanded=False):
        st.markdown("**會清空的資料表**")
        st.code("\n".join(target_tables), language="text")
        st.markdown("**會重設的 id_sequences key**")
        st.code("\n".join(target_sequence_keys), language="text")
        st.markdown("**不會動到的資料**")
        st.code("vendors\nunits\nitems\nprices\nusers\nstores\nbrands\nsettings", language="text")

    confirm_text = st.text_input("請輸入 RESET 才能執行初始化", key="system_reset_confirm")
    can_run = app_runtime.is_system_reset_confirmed(confirm_text)

    if st.button("🗑️ 初始化庫存 / 叫貨 / 序號", width="stretch", type="primary", disabled=not can_run):
        try:
            app_runtime.run_system_reset(
                target_tables=target_tables,
                target_sequence_keys=target_sequence_keys,
                actor=st.session_state.get("login_user", "system"),
            )
            st.success("✅ 初始化完成：庫存、叫貨、交易資料已清空，對應序號已重設。")
            st.rerun()

        except Exception as e:
            st.error(f"❌ 初始化失敗：{e}")

    st.markdown("---")
    st.markdown("### Sequence 檢查")
    seq_df = app_runtime.load_id_sequences_view()
    if seq_df.empty:
        st.info("目前讀不到 id_sequences 資料")
    else:
        st.dataframe(seq_df, width="stretch", hide_index=True)

    if st.button("⬅️ 返回", width="stretch", key="back_from_system_maintenance"):
        st.session_state.step = "select_store"
        st.rerun()
