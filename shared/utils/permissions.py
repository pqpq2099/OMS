from __future__ import annotations

# ============================================================
# ORIVIA OMS
# 檔案：shared/utils/permissions.py
# 說明：統一權限與資料範圍工具
# 功能：
#   - require_permission：守衛式判斷，無權限顯示提示並回傳 False
#   - has_store_access：判斷使用者是否可存取特定門市
#   - filter_stores_by_scope：過濾 DataFrame 至使用者可存取門市
# 注意：
#   - 不寫死角色名稱，全部走 permissions / role_permissions 表
#   - 不修改登入流程，不接 Supabase Auth，不啟用 RLS
# ============================================================

import streamlit as st

from users_permissions.services.service_role_permission import has_permission


def require_permission(permission_key: str, message: str = "您沒有此功能的存取權限") -> bool:
    """
    守衛式權限判斷：
    - 有權限 → 回傳 True，頁面繼續執行
    - 無權限 → 顯示 warning 並回傳 False，頁面應 return

    使用方式：
        if not require_permission("order.view"):
            return
    """
    if not has_permission(permission_key):
        st.warning(f"⚠️ {message}")
        return False
    return True


def has_store_access(store_id: str) -> bool:
    """
    判斷目前登入者是否可存取指定 store_id。
    - store_scope == "ALL" 或為空 → 全部可存取
    - 否則僅允許 store_scope 對應的門市
    """
    scope = str(st.session_state.get("login_store_scope", "")).strip()
    if not scope or scope.upper() == "ALL":
        return True
    return str(store_id).strip() == scope


def filter_stores_by_scope(stores_df):
    """
    依 login_store_scope 過濾門市 DataFrame。
    - ALL 或空值 → 回傳原始 DataFrame（不過濾）
    - 特定 store_id → 僅回傳該門市的列

    不修改傳入的 DataFrame，回傳新的 copy。
    """
    if stores_df is None or stores_df.empty:
        return stores_df
    scope = str(st.session_state.get("login_store_scope", "")).strip()
    if not scope or scope.upper() == "ALL":
        return stores_df
    filtered = stores_df[
        stores_df["store_id"].astype(str).str.strip() == scope
    ].copy()
    return filtered
