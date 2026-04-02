from __future__ import annotations

import streamlit as st

from shared.utils.ui_style import apply_global_style
import shared.core.app_runtime as app_runtime
from shared.core.navigation import goto, render_step_buttons, route_step
import operations.pages as operations_pages
import analysis.pages as analysis_pages
import data_management.pages as data_management_pages
import users_permissions.pages as users_permissions_pages
import system.pages as system_pages



def render_sidebar():
    role = st.session_state.get("login_role_id", "")
    system_name = app_runtime.get_system_name()
    logo_url = app_runtime.get_setting_value("logo_url", "").strip()

    operation_items = [
        {"label": "🏠 選擇分店", "step": "select_store", "key": "sb_select_store"},
        {"label": "🧾 叫貨明細", "step": "order_message_detail", "key": "sb_order_message_detail"},
        {"label": "📄 庫存＋叫貨對照表", "step": "stock_order_compare", "key": "sb_stock_order_compare"},
    ]

    analysis_items = [
        {"label": "📊 進銷存分析", "step": "analysis", "key": "sb_analysis"},
        {"label": "📦 歷史叫貨紀錄", "step": "view_history", "key": "sb_view_history"},
        {"label": "📤 資料匯出", "step": "export", "key": "sb_export"},
    ]

    data_items = [
        {
            "label": "🛒 採購設定",
            "step": "purchase_settings",
            "key": "sb_purchase_settings",
            "visible": role in ["owner", "admin"],
        },
        {
            "label": "🧮 成本檢查",
            "step": "cost_debug",
            "key": "sb_cost_debug",
            "visible": role in ["owner", "admin"],
        },
        {
            "label": "🏬 分店管理",
            "step": "store_admin",
            "key": "sb_store_admin",
            "visible": role in ["owner", "admin"],
        },
    ]

    user_items = [
        {
            "label": "👥 使用者管理",
            "step": "user_admin",
            "key": "sb_user_admin",
            "visible": role in ["owner", "admin"],
        },
        {"label": "🙍 個人帳號管理", "step": "account_settings", "key": "sb_account_settings"},
    ]

    system_items = [
        {
            "label": "🎨 系統外觀",
            "step": "appearance_settings",
            "key": "sb_appearance_settings",
            "visible": role in ["owner", "admin"],
        },
        {
            "label": "ℹ️ 系統資訊",
            "step": "system_info",
            "key": "sb_system_info",
            "visible": role in ["owner", "admin"],
        },
    ]

    with st.sidebar:
        if logo_url:
            try:
                st.image(logo_url, width=140)
            except Exception:
                st.caption("Logo 載入失敗")

        st.markdown(f"## {system_name}")

        st.markdown("### 作業")
        render_step_buttons(operation_items)
        st.markdown("---")

        st.markdown("### 分析")
        render_step_buttons(analysis_items)
        st.markdown("---")

        st.markdown("### 資料管理")
        render_step_buttons(data_items)
        st.markdown("---")

        st.markdown("### 使用者與權限")
        render_step_buttons(user_items)
        st.markdown("---")

        users_permissions_pages.render_login_sidebar()

        if role in ["owner", "admin"]:
            st.markdown("### 系統")
            render_step_buttons(system_items)

            if role == "owner":
                if app_runtime.is_bypass_mode():
                    if app_runtime.has_locked_system_access():
                        verified_name = st.session_state.get("owner_gate_display_name", "")
                        if verified_name:
                            st.caption(f"已驗證：{verified_name}")

                        if st.button("🛠 系統維護", width="stretch", key="sb_system_maintenance"):
                            goto("system_maintenance")

                        if st.button("🧰 系統工具", width="stretch", key="sb_system_tools"):
                            goto("system_tools")

                        if st.button("🔓 登出系統管理", width="stretch", key="sb_owner_gate_logout"):
                            app_runtime.clear_locked_system_access()
                            goto("select_store")
                    else:
                        if st.button("🔐 系統管理登入", width="stretch", key="sb_owner_verify"):
                            app_runtime.go_owner_verify("system_tools")
                else:
                    if st.button("🛠 系統維護", width="stretch", key="sb_system_maintenance"):
                        goto("system_maintenance")

                    if st.button("🧰 系統工具", width="stretch", key="sb_system_tools"):
                        goto("system_tools")


def router():
    step = st.session_state.step

    routes = {
        "select_store": operations_pages.page_select_store,
        "select_vendor": operations_pages.page_select_vendor,
        "order_entry": operations_pages.page_order,
        "order_message_detail": operations_pages.page_order_message_detail,
        "purchase_orders": operations_pages.page_purchase_orders,
        "stocktake_history": operations_pages.page_stocktake_history,
        "export": analysis_pages.page_export,
        "stock_order_compare": analysis_pages.page_stock_order_compare,
        "analysis": analysis_pages.page_analysis,
        "view_history": analysis_pages.page_view_history,
        "cost_debug": analysis_pages.page_cost_debug,
        "appearance_settings": system_pages.page_appearance_settings,
        "system_info": system_pages.page_system_info,
        "owner_verify": app_runtime.page_owner_verify,
        "user_admin": users_permissions_pages.page_user_admin,
        "account_settings": users_permissions_pages.page_account_settings,
        "purchase_settings": data_management_pages.page_purchase_settings,
        "store_admin": users_permissions_pages.page_store_admin,
        "system_maintenance": system_pages.page_system_maintenance,
        "system_tools": system_pages.page_system_tools,
    }

    route_step(step, routes, operations_pages.page_select_store)


def run_app():
    st.set_page_config(page_title="營運管理系統", layout="centered")
    apply_global_style()
    app_runtime.initialize_runtime()
    render_sidebar()
    # [TEMP DEBUG] Supabase 連線診斷 — 確認後可移除此區塊
    from shared.services.supabase_client import debug_connection_info as _dci
    with st.sidebar.expander("🔍 連線診斷 [TEMP]", expanded=False):
        _info = _dci()
        st.caption(f"URL: `{_info['masked_url']}`")
        st.caption(f"Key 已設定: `{_info['has_key']}`")
        st.caption(f"id_sequences 可讀: {'✅' if _info['seq_exists'] else '❌'}")
        st.caption(f"id_sequences 筆數: `{_info['seq_count']}`")
        st.caption(f"stocktakes seq: {'✅' if _info['stocktake_seq'] else '❌'}")
        st.caption(f"purchase_orders seq: {'✅' if _info['order_seq'] else '❌'}")
        st.caption(f"stocktake_lines/pol seq: {'✅' if _info['stock_seq'] else '❌'}")
        if _info['error_msg']:
            st.error(f"❌ {_info['error_msg']}")
    # [END TEMP DEBUG]
    router()
