# ============================================================
# ORIVIA OMS
# 檔案：pages/page_login.py
# 說明：登入頁面
# 功能：帳號登入、權限載入、登入狀態建立。
# 注意：登入成功後會把角色與分店範圍寫入 session_state。
# ============================================================

"""
頁面模組：登入 / 首次初始化 / 修改密碼

功能：
1. 第一次啟用時，若 owner 帳號存在但尚未設定密碼，顯示初始化畫面
2. 一般帳號密碼登入
3. 若 must_change_password = 1，登入後強制修改密碼
4. 支援 sidebar 顯示目前登入者與登出按鈕

資料來源：
Google Sheet
- users

設計原則：
- 密碼只存 hash，不存明碼
- owner 第一次可直接在系統中設定初始密碼
- 布林欄位一律使用 1 / 0
"""

from __future__ import annotations

import streamlit as st

from users_permissions.services.service_users import (
    UserServiceError,
    norm_text,
    role_label,
)
from users_permissions.logic.logic_login import (
    build_login_page_view_state,
    preload_login_users,
    submit_force_change_password,
    submit_login,
    submit_owner_initialize,
)


# ============================================================
# [A] 基本工具
# ============================================================
def _set_login_session_payload(payload: dict[str, object]):
    for key, value in payload.items():
        st.session_state[key] = value


def _set_login_session(user_row: pd.Series):
    payload = {
        "login_user": norm_text(user_row.get("user_id")),
        "login_account_code": norm_text(user_row.get("account_code")),
        "login_display_name": norm_text(user_row.get("display_name")),
        "login_role_id": norm_text(user_row.get("role_id")).lower(),
        "login_store_scope": norm_text(user_row.get("store_scope")),
        "force_change_password": str(user_row.get("must_change_password", "")).strip() in {"1", "true", "True"},
    }
    _set_login_session_payload(payload)


def logout():
    """清除登入狀態。"""
    for key in [
        "login_user",
        "login_account_code",
        "login_display_name",
        "login_role_id",
        "login_store_scope",
        "force_change_password",
    ]:
        if key in st.session_state:
            del st.session_state[key]


def _role_label_zh(role_id: str) -> str:
    """將角色代碼轉成中文顯示，sidebar 不再直接顯示英文代碼。"""
    return role_label(role_id)


def render_login_sidebar():
    """在 sidebar 顯示目前登入者資訊與登出按鈕。"""
    if "login_user" not in st.session_state:
        return

    st.sidebar.markdown("---")
    st.sidebar.caption("目前登入")
    st.sidebar.write(st.session_state.get("login_display_name", ""))
    role_id = st.session_state.get("login_role_id", "")
    st.sidebar.caption(
        f"{st.session_state.get('login_account_code', '')} / "
        f"{_role_label_zh(role_id)}"
    )

    if st.sidebar.button("登出", use_container_width=True, key="btn_logout"):
        logout()
        st.rerun()


# ============================================================
# [B] 首次初始化：owner 尚未設定密碼
# ============================================================
def _page_owner_first_setup(owner_row: pd.Series):
    """
    當 users 表中已有 owner，但 password_hash 仍是空白時，
    顯示第一次初始化密碼畫面。
    """
    st.title("🔐 系統首次初始化")
    st.info("已偵測到系統擁有者帳號，請先設定第一次登入密碼。")

    st.write(f"帳號：`{norm_text(owner_row.get('account_code'))}`")
    st.write(f"名稱：{norm_text(owner_row.get('display_name'))}")

    with st.form("owner_first_setup_form"):
        new_password = st.text_input("請設定密碼", type="password", key="owner_init_pw")
        confirm_password = st.text_input("再次輸入密碼", type="password", key="owner_init_pw2")
        submitted = st.form_submit_button("完成初始化", use_container_width=True)

    if submitted:
        try:
            submit_owner_initialize(
                norm_text(owner_row.get("user_id")),
                new_password,
                confirm_password,
            )
            st.success("初始化完成，請直接登入。")
            st.rerun()
        except UserServiceError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"初始化失敗：{e}")


# ============================================================
# [C] 強制修改密碼
# ============================================================
def _page_force_change_password():
    """
    若使用者 must_change_password = 1，
    登入後必須先改密碼，才能繼續進系統。
    """
    st.title("🔐 請先修改密碼")
    st.warning("此帳號為初始密碼或臨時密碼，請先修改後再使用系統。")

    with st.form("force_change_password_form"):
        new_password = st.text_input("新密碼", type="password", key="force_pw_1")
        confirm_password = st.text_input("再次輸入新密碼", type="password", key="force_pw_2")
        submitted = st.form_submit_button("更新密碼", use_container_width=True)

    if submitted:
        try:
            submit_force_change_password(
                st.session_state.get("login_user", ""),
                new_password,
                confirm_password,
            )
            st.session_state["force_change_password"] = False
            st.success("密碼更新成功。")
            st.rerun()
        except UserServiceError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"更新密碼失敗：{e}")


# ============================================================
# [D] 一般登入頁
# ============================================================
def _page_normal_login():
    """一般登入畫面（支援 Enter 直接登入）。"""
    st.title("🔑 系統登入")

    with st.form("login_form"):
        account = st.text_input("帳號", key="login_account_input")
        password = st.text_input("密碼", type="password", key="login_password_input")
        submitted = st.form_submit_button("登入", use_container_width=True)

    if submitted:
        try:
            payload = submit_login(account, password)
            _set_login_session_payload(payload)
            st.success("登入成功。")
            st.rerun()
        except UserServiceError as e:
            st.error(str(e))


# ============================================================
# [E] 主入口：依情況切換畫面
# ============================================================
def page_login():
    """
    登入主入口：
    1. 若已有登入，且需強制改密碼 → 顯示改密碼頁
    2. 若 users 表中的 owner 尚未設定密碼 → 顯示首次初始化頁
    3. 否則顯示一般登入頁
    """
    preload_login_users()  # 保留 users 表預讀，避免切頁時首次顯示延遲

    page_view_state = build_login_page_view_state(
        has_login_user="login_user" in st.session_state,
        force_change_password=bool(st.session_state.get("force_change_password", False)),
    )
    page_state = page_view_state["page_state"]
    owner_row = page_view_state["owner_row"]
    if page_state == "force_change_password":
        _page_force_change_password()
        return
    if page_state == "owner_first_setup":
        _page_owner_first_setup(owner_row)
        return

    _page_normal_login()
