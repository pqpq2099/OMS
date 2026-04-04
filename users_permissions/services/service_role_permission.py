from __future__ import annotations

# ============================================================
# ORIVIA OMS
# 檔案：users_permissions/services/service_role_permission.py
# 說明：角色與權限查詢服務
# 功能：從 Supabase 讀取角色對應的 permission_key 清單，
#       並提供統一的 has_permission 判斷介面。
# 注意：不修改登入流程，不接 Supabase Auth，不啟用 RLS。
#       登入後由 load_user_permissions_to_session 載入至
#       st.session_state["current_permissions"]。
# ============================================================

import streamlit as st

from shared.services.supabase_client import fetch_table


# ----------------------------------------------------------------
# 內部工具
# ----------------------------------------------------------------

def _fetch_permissions_for_role(role_id: str) -> list[str]:
    """
    從 role_permissions + permissions 查詢指定 role 的 permission_key 清單。
    若查詢失敗則回傳空清單，不拋出例外。
    """
    if not role_id:
        return []
    try:
        rp_rows = fetch_table("role_permissions")
        perm_rows = fetch_table("permissions")

        role_perm_ids = {
            str(r.get("permission_id", "")).strip()
            for r in rp_rows
            if str(r.get("role_id", "")).strip().lower() == role_id.lower()
        }

        keys = [
            str(r.get("permission_key", "")).strip()
            for r in perm_rows
            if str(r.get("permission_id", "")).strip() in role_perm_ids
            and str(r.get("permission_key", "")).strip()
        ]
        return keys
    except Exception:
        return []


def _role_fallback_permissions(role_id: str) -> list[str]:
    """
    DB 查詢失敗時的備援：依 role_id 回傳預設 permission_key 清單。
    確保系統在 permissions 表不可用時仍可正常運作。
    """
    base_ops = ["order.view", "order.create", "analysis.view"]
    store_manager_perms = base_ops + ["order.submit", "order.send_line"]
    admin_perms = store_manager_perms + [
        "manage_purchase_settings",
        "manage_store",
        "manage_users",
        "user.manage",
        "view_system_info",
        "view_cost_debug",
    ]
    owner_perms = admin_perms + ["manage_system"]

    staff_perms = base_ops + ["transfer.view"]
    leader_perms = base_ops + ["order.submit", "analysis.export", "transfer.view", "operation.transfer.execute"]
    store_manager_perms = leader_perms + ["order.send_line", "transfer.create", "operation.stock.adjust"]
    admin_perms = store_manager_perms + [
        "manage_purchase_settings",
        "manage_store",
        "manage_users",
        "user.manage",
        "users.manage",
        "view_system_info",
        "view_cost_debug",
        "analysis.export",
        "transfer.create",
    ]
    owner_perms = admin_perms + ["manage_system", "system.manage"]

    role = (role_id or "").lower()
    if role == "owner":
        return owner_perms
    if role in ("admin", "test_admin"):
        return admin_perms
    if role in ("store_manager", "test_store_manager"):
        return store_manager_perms
    if role in ("leader", "test_leader"):
        return leader_perms
    if role == "staff":
        return staff_perms
    if role == "pt":
        return ["order.view"]
    return []


# ----------------------------------------------------------------
# 對外介面
# ----------------------------------------------------------------

def load_user_permissions_to_session(role_id: str) -> None:
    """
    登入後（或首次渲染時）載入 permission_key 清單至 session_state。
    - current_permissions: list[str]
    - current_role: str（role_id）

    若 DB 查詢失敗，自動 fallback 至角色預設清單。
    """
    if not role_id:
        st.session_state["current_permissions"] = []
        st.session_state["current_role"] = ""
        return

    perms = _fetch_permissions_for_role(role_id)
    if not perms:
        perms = _role_fallback_permissions(role_id)

    st.session_state["current_permissions"] = perms
    st.session_state["current_role"] = role_id.lower()


def has_permission(permission_key: str) -> bool:
    """
    檢查目前登入者是否擁有指定的 permission_key。
    若 current_permissions 尚未載入，回傳 False。
    """
    perms = st.session_state.get("current_permissions")
    if not isinstance(perms, list):
        return False
    return permission_key in perms


def clear_permissions_session() -> None:
    """登出時清除 permission 相關 session_state。"""
    for key in ("current_permissions", "current_role"):
        st.session_state.pop(key, None)
