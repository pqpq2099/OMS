from __future__ import annotations

from datetime import date

import streamlit as st
from pages_user_admin import page_user_admin
from oms_core import apply_global_style

from pages_order import (
    page_order_entry,
    page_select_store,
    page_select_vendor,
)

from pages_reports import (
    page_analysis,
    page_cost_debug,
    page_export,
    page_view_history,
)

st.set_page_config(page_title="OMS 系統", layout="centered")


# ============================================================
# Session State
# ============================================================
def init_session():
    if "step" not in st.session_state:
        st.session_state.step = "select_store"
    if "record_date" not in st.session_state:
        st.session_state.record_date = date.today()
    if "store_id" not in st.session_state:
        st.session_state.store_id = ""
    if "store_name" not in st.session_state:
        st.session_state.store_name = ""
    if "vendor_id" not in st.session_state:
        st.session_state.vendor_id = ""
    if "vendor_name" not in st.session_state:
        st.session_state.vendor_name = ""

    # 先用假角色測試，之後再接 users / roles
    if "role" not in st.session_state:
        st.session_state.role = "owner"  # owner / admin / store_manager / leader


# ============================================================
# Placeholder
# ============================================================
def page_placeholder(title: str, desc: str = "此功能入口已建立，功能尚未接上。"):
    st.title(title)
    st.info(desc)
    st.markdown("---")
    st.caption("目前為占位頁，之後會接正式功能。")


# ============================================================
# Sidebar
# ============================================================
def render_sidebar():
    role = st.session_state.role

    with st.sidebar:
        st.markdown("## ORIVIA OMS")
        st.caption("OMS Modular Baseline")

        if st.session_state.store_name:
            st.write(f"**分店：** {st.session_state.store_name}")
        if st.session_state.vendor_name:
            st.write(f"**廠商：** {st.session_state.vendor_name}")

        st.caption(f"目前角色：{role}")
        st.markdown("---")

        # ====================================================
        # 首頁
        # ====================================================
        if st.button("🏠 選擇分店", use_container_width=True, key="sb_select_store"):
            st.session_state.step = "select_store"
            st.rerun()

        # ====================================================
        # 作業管理
        # ====================================================
        st.markdown("### 作業管理")

        if st.session_state.store_id:
            if st.button("🏢 分店功能選單", use_container_width=True, key="sb_select_vendor"):
                st.session_state.step = "select_vendor"
                st.rerun()

        if st.session_state.vendor_id:
            if st.button("📝 叫貨 / 庫存", use_container_width=True, key="sb_order_entry"):
                st.session_state.step = "order_entry"
                st.rerun()

        if st.session_state.store_id:
            if st.button("📋 今日進貨明細", use_container_width=True, key="sb_export"):
                st.session_state.step = "export"
                st.rerun()

        # ====================================================
        # 報表分析
        # ====================================================
        if role in ["owner", "admin", "store_manager"]:
            st.markdown("### 報表分析")

            if st.session_state.store_id:
                if st.button("📈 進銷存分析", use_container_width=True, key="sb_analysis"):
                    st.session_state.step = "analysis"
                    st.rerun()

                if st.button("📜 歷史紀錄", use_container_width=True, key="sb_view_history"):
                    st.session_state.step = "view_history"
                    st.rerun()

                if st.button("📤 資料匯出", use_container_width=True, key="sb_data_export"):
                    st.session_state.step = "data_export"
                    st.rerun()

        # ====================================================
        # 後台管理
        # ====================================================
        if role in ["owner", "admin"]:
            st.markdown("### 後台管理")

            if st.button("👥 使用者權限", use_container_width=True, key="sb_user_admin"):
                st.session_state.step = "user_admin"
                st.rerun()

            if st.button("🛒 採購設定", use_container_width=True, key="sb_purchase_settings"):
                st.session_state.step = "purchase_settings"
                st.rerun()

            if st.button("🧮 成本檢查", use_container_width=True, key="sb_cost_debug"):
                st.session_state.step = "cost_debug"
                st.rerun()

            if st.button("🎨 系統外觀", use_container_width=True, key="sb_appearance_settings"):
                st.session_state.step = "appearance_settings"
                st.rerun()

        # ====================================================
        # 系統工具（Owner only）
        # ====================================================
        if role == "owner":
            st.markdown("### 系統工具")

            if st.button("🛠️ 系統工具", use_container_width=True, key="sb_system_tools"):
                st.session_state.step = "system_tools"
                st.rerun()

            if st.button("🧪 開發測試", use_container_width=True, key="sb_dev_test"):
                st.session_state.step = "dev_test"
                st.rerun()


# ============================================================
# Router
# ============================================================
def router():
    step = st.session_state.step

    # ---------------------------
    # 正式已完成頁面
    # ---------------------------
    if step == "select_store":
        page_select_store()

    elif step == "select_vendor":
        page_select_vendor()
    elif step == "order_entry":
        page_order_entry()
    elif step == "export":
        page_export()
    elif step == "analysis":
        page_analysis()
    elif step == "view_history":
        page_view_history()
    elif step == "user_admin":
        page_user_admin()
    elif step == "cost_debug":
        page_cost_debug()

    # ---------------------------
    # 入口先建立，功能待接
    # ---------------------------
    elif step == "data_export":
        page_placeholder("📤 資料匯出")

    elif step == "user_admin":
        page_placeholder("👥 使用者權限")

    elif step == "purchase_settings":
        page_placeholder("🛒 採購設定")

    elif step == "appearance_settings":
        page_placeholder("🎨 系統外觀")

    elif step == "system_tools":
        page_placeholder("🛠️ 系統工具")

    elif step == "dev_test":
        page_placeholder("🧪 開發測試")

    else:
        page_select_store()


# ============================================================
# Main
# ============================================================
def main():
    apply_global_style()
    init_session()
    render_sidebar()
    router()


if __name__ == "__main__":
    main()

