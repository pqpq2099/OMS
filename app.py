from __future__ import annotations

from datetime import date

import streamlit as st

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

    # 先用固定角色當測試，之後再接 users / roles
    if "role" not in st.session_state:
        st.session_state.role = "owner"  # owner / admin / store_manager / leader


# ============================================================
# Placeholder Page
# ============================================================
def page_placeholder(title: str, desc: str = "此功能入口已建立，功能尚未接上。"):
    st.title(title)
    st.info(desc)

    st.markdown("---")
    st.caption("目前為占位頁。之後功能完成後，這裡會接正式頁面。")


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

        # ----------------------------------------------------
        # 首頁 / 基本入口
        # ----------------------------------------------------
        st.markdown("### 首頁")
        if st.button("🏠 選擇分店", use_container_width=True, key="sb_select_store"):
            st.session_state.step = "select_store"
            st.rerun()

        # ----------------------------------------------------
        # 門市操作
        # ----------------------------------------------------
        st.markdown("### 門市操作")

        if st.session_state.store_id:
            if st.button("🏢 分店功能選單", use_container_width=True, key="sb_select_vendor"):
                st.session_state.step = "select_vendor"
                st.rerun()

        if st.session_state.vendor_id:
            if st.button("📝 叫貨 / 庫存", use_container_width=True, key="sb_order_entry"):
                st.session_state.step = "order_entry"
                st.rerun()

        if role in ["owner", "admin", "store_manager"]:
            if st.button("🛠️ 庫存修正", use_container_width=True, key="sb_stock_adjust"):
                st.session_state.step = "stock_adjust"
                st.rerun()

            if st.button("📦 到貨修正", use_container_width=True, key="sb_delivery_adjust"):
                st.session_state.step = "delivery_adjust"
                st.rerun()

        # ----------------------------------------------------
        # 報表分析
        # ----------------------------------------------------
        st.markdown("### 報表分析")

        if st.session_state.store_id:
            if st.button("📋 今日進貨明細", use_container_width=True, key="sb_export"):
                st.session_state.step = "export"
                st.rerun()

            if st.button("🧾 歷史叫貨紀錄", use_container_width=True, key="sb_purchase_history"):
                st.session_state.step = "purchase_history"
                st.rerun()

            if st.button("📈 期間進銷存分析", use_container_width=True, key="sb_analysis"):
                st.session_state.step = "analysis"
                st.rerun()

            if st.button("📜 歷史庫存紀錄", use_container_width=True, key="sb_view_history"):
                st.session_state.step = "view_history"
                st.rerun()

            if st.button("🧮 成本檢查", use_container_width=True, key="sb_cost_debug"):
                st.session_state.step = "cost_debug"
                st.rerun()

        # ----------------------------------------------------
        # 系統管理
        # ----------------------------------------------------
        if role in ["owner", "admin"]:
            st.markdown("### 系統管理")

            if st.button("🏬 分店管理", use_container_width=True, key="sb_store_admin"):
                st.session_state.step = "store_admin"
                st.rerun()

            if st.button("🚚 廠商管理", use_container_width=True, key="sb_vendor_admin"):
                st.session_state.step = "vendor_admin"
                st.rerun()

            if st.button("📦 品項管理", use_container_width=True, key="sb_item_admin"):
                st.session_state.step = "item_admin"
                st.rerun()

            if st.button("🔄 單位 / 換算管理", use_container_width=True, key="sb_unit_admin"):
                st.session_state.step = "unit_admin"
                st.rerun()

            if st.button("💲 價格管理", use_container_width=True, key="sb_price_admin"):
                st.session_state.step = "price_admin"
                st.rerun()

            if st.button("👥 使用者 / 權限", use_container_width=True, key="sb_user_admin"):
                st.session_state.step = "user_admin"
                st.rerun()

            if st.button("🧭 店長指派", use_container_width=True, key="sb_manager_assign"):
                st.session_state.step = "manager_assign"
                st.rerun()

        # ----------------------------------------------------
        # 系統工具
        # ----------------------------------------------------
        if role in ["owner", "admin"]:
            st.markdown("### 系統工具")

            if st.button("📤 資料匯出", use_container_width=True, key="sb_data_export"):
                st.session_state.step = "data_export"
                st.rerun()

            if st.button("📝 Audit Log", use_container_width=True, key="sb_audit_log"):
                st.session_state.step = "audit_log"
                st.rerun()

            if st.button("ℹ️ 系統資訊", use_container_width=True, key="sb_system_info"):
                st.session_state.step = "system_info"
                st.rerun()

        # ----------------------------------------------------
        # 開發 / 測試
        # ----------------------------------------------------
        if role == "owner":
            st.markdown("### 開發 / 測試")

            if st.button("🧪 測試頁", use_container_width=True, key="sb_test_page"):
                st.session_state.step = "test_page"
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

    elif step == "cost_debug":
        page_cost_debug()

    elif step == "view_history":
        page_view_history()

    # ---------------------------
    # 先做入口、功能未完成頁面
    # ---------------------------
    elif step == "purchase_history":
        page_placeholder("🧾 歷史叫貨紀錄")

    elif step == "stock_adjust":
        page_placeholder("🛠️ 庫存修正")

    elif step == "delivery_adjust":
        page_placeholder("📦 到貨修正")

    elif step == "store_admin":
        page_placeholder("🏬 分店管理")

    elif step == "vendor_admin":
        page_placeholder("🚚 廠商管理")

    elif step == "item_admin":
        page_placeholder("📦 品項管理")

    elif step == "unit_admin":
        page_placeholder("🔄 單位 / 換算管理")

    elif step == "price_admin":
        page_placeholder("💲 價格管理")

    elif step == "user_admin":
        page_placeholder("👥 使用者 / 權限")

    elif step == "manager_assign":
        page_placeholder("🧭 店長指派")

    elif step == "data_export":
        page_placeholder("📤 資料匯出")

    elif step == "audit_log":
        page_placeholder("📝 Audit Log")

    elif step == "system_info":
        page_placeholder("ℹ️ 系統資訊")

    elif step == "test_page":
        page_placeholder("🧪 測試頁")

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
