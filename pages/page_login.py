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

from datetime import datetime
import hashlib

import pandas as pd
import streamlit as st

from oms_core import get_spreadsheet, read_table


# ============================================================
# [A] 基本工具
# ============================================================
def _now_ts() -> str:
    """回傳目前時間字串。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _norm_text(value) -> str:
    """安全轉字串，避免 NaN / None 造成比對錯誤。"""
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _norm_10(value) -> int:
    """
    將各種可能格式轉成 1 / 0。
    支援：1, 0, True, False, '1', '0', 'true', 'false'
    """
    text = _norm_text(value).lower()
    return 1 if text in {"1", "true", "yes", "y"} else 0


def _sha256(password: str) -> str:
    """將密碼做 SHA256 雜湊。"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _load_users_df() -> pd.DataFrame:
    """讀取 users 表，並補齊常用欄位。"""
    df = read_table("users").copy()

    if df.empty:
        return df

    for col in [
        "user_id",
        "account_code",
        "email",
        "display_name",
        "password_hash",
        "must_change_password",
        "role_id",
        "store_scope",
        "is_active",
        "last_login_at",
        "created_at",
        "updated_at",
    ]:
        if col not in df.columns:
            df[col] = ""

    return df


def _find_row_index_by_user_id(user_id: str) -> int | None:
    """
    在 Google Sheet 的 users 分頁中，找到對應 user_id 的實際列號。
    例如：第 2 列、第 3 列...
    """
    sh = get_spreadsheet()
    ws = sh.worksheet("users")
    values = ws.get_all_values()

    if not values:
        return None

    headers = values[0]
    if "user_id" not in headers:
        return None

    user_col_idx = headers.index("user_id")

    for row_idx, row in enumerate(values[1:], start=2):
        cell_value = row[user_col_idx] if user_col_idx < len(row) else ""
        if _norm_text(cell_value) == _norm_text(user_id):
            return row_idx

    return None


def _update_user_fields(user_id: str, updates: dict):
    """
    直接更新 users 表中的某一筆使用者資料。
    使用 user_id 當唯一識別鍵。
    """
    sh = get_spreadsheet()
    ws = sh.worksheet("users")
    values = ws.get_all_values()

    if not values:
        raise ValueError("users 分頁為空，無法更新資料。")

    headers = values[0]
    row_idx = _find_row_index_by_user_id(user_id)

    if row_idx is None:
        raise ValueError(f"找不到 user_id：{user_id}")

    for field, value in updates.items():
        if field not in headers:
            continue

        col_idx = headers.index(field) + 1
        ws.update_cell(row_idx, col_idx, value)


def _set_login_session(user_row: pd.Series):
    """登入成功後，將必要資料寫入 session_state。"""
    st.session_state["login_user"] = _norm_text(user_row.get("user_id"))
    st.session_state["login_account_code"] = _norm_text(user_row.get("account_code"))
    st.session_state["login_display_name"] = _norm_text(user_row.get("display_name"))
    st.session_state["login_role_id"] = _norm_text(user_row.get("role_id")).lower()
    st.session_state["login_store_scope"] = _norm_text(user_row.get("store_scope"))
    st.session_state["force_change_password"] = _norm_10(user_row.get("must_change_password")) == 1


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
    mapping = {
        "owner": "負責人",
        "admin": "管理員",
        "store_manager": "店長",
        "leader": "組長",
        "staff": "一般員工",
        "employee": "一般員工",
        "test_admin": "測試管理員",
        "test_store_manager": "測試店長",
    }
    rid = _norm_text(role_id).lower()
    return mapping.get(rid, rid)


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

    st.write(f"帳號：`{_norm_text(owner_row.get('account_code'))}`")
    st.write(f"名稱：{_norm_text(owner_row.get('display_name'))}")

    new_password = st.text_input("請設定密碼", type="password", key="owner_init_pw")
    confirm_password = st.text_input("再次輸入密碼", type="password", key="owner_init_pw2")

    if st.button("完成初始化", use_container_width=True, key="btn_owner_init"):
        if not new_password or not confirm_password:
            st.error("請完整輸入密碼與確認密碼。")
            return

        if len(new_password) < 6:
            st.error("密碼至少 6 碼。")
            return

        if new_password != confirm_password:
            st.error("兩次輸入的密碼不一致。")
            return

        try:
            _update_user_fields(
                _norm_text(owner_row.get("user_id")),
                {
                    "password_hash": _sha256(new_password),
                    "must_change_password": 0,
                    "updated_at": _now_ts(),
                },
            )
            st.success("初始化完成，請直接登入。")
            st.rerun()
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

    new_password = st.text_input("新密碼", type="password", key="force_pw_1")
    confirm_password = st.text_input("再次輸入新密碼", type="password", key="force_pw_2")

    if st.button("更新密碼", use_container_width=True, key="btn_force_change_pw"):
        if "login_user" not in st.session_state:
            st.error("登入狀態遺失，請重新登入。")
            return

        if not new_password or not confirm_password:
            st.error("請完整輸入新密碼。")
            return

        if len(new_password) < 6:
            st.error("密碼至少 6 碼。")
            return

        if new_password != confirm_password:
            st.error("兩次輸入的密碼不一致。")
            return

        try:
            _update_user_fields(
                st.session_state["login_user"],
                {
                    "password_hash": _sha256(new_password),
                    "must_change_password": 0,
                    "updated_at": _now_ts(),
                },
            )
            st.session_state["force_change_password"] = False
            st.success("密碼更新成功。")
            st.rerun()
        except Exception as e:
            st.error(f"更新密碼失敗：{e}")


# ============================================================
# [D] 一般登入頁
# ============================================================
def _page_normal_login():
    """一般登入畫面。"""
    st.title("🔑 系統登入")

    account = st.text_input("帳號", key="login_account_input")
    password = st.text_input("密碼", type="password", key="login_password_input")

    if st.button("登入", use_container_width=True, key="btn_login_submit"):
        users_df = _load_users_df()

        if users_df.empty:
            st.error("users 資料表為空，無法登入。")
            return

        work = users_df.copy()
        work["account_code"] = work["account_code"].apply(_norm_text)
        work["password_hash"] = work["password_hash"].apply(_norm_text)
        work["role_id"] = work["role_id"].apply(lambda x: _norm_text(x).lower())
        work["is_active"] = work["is_active"].apply(_norm_10)

        target = work[
            (work["account_code"] == _norm_text(account)) &
            (work["is_active"] == 1)
        ]

        if target.empty:
            st.error("帳號不存在，或此帳號未啟用。")
            return

        user_row = target.iloc[0]

        if _norm_text(user_row.get("password_hash")) != _sha256(password):
            st.error("密碼錯誤。")
            return

        try:
            _update_user_fields(
                _norm_text(user_row.get("user_id")),
                {
                    "last_login_at": _now_ts(),
                    "updated_at": _now_ts(),
                },
            )
        except Exception:
            # 登入不因 last_login 更新失敗而中斷
            pass

        _set_login_session(user_row)
        st.success("登入成功。")
        st.rerun()


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
    users_df = _load_users_df()

    # 1) 已登入但必須強制改密碼
    if (
        "login_user" in st.session_state
        and st.session_state.get("force_change_password", False)
    ):
        _page_force_change_password()
        return

    # 2) 找 owner
    if not users_df.empty:
        work = users_df.copy()
        work["role_id"] = work["role_id"].apply(lambda x: _norm_text(x).lower())
        work["is_active"] = work["is_active"].apply(_norm_10)
        work["password_hash"] = work["password_hash"].apply(_norm_text)

        owner_df = work[
            (work["role_id"] == "owner") &
            (work["is_active"] == 1)
        ]

        # 有 owner，但尚未設定密碼 → 首次初始化
        if not owner_df.empty:
            owner_row = owner_df.iloc[0]
            if _norm_text(owner_row.get("password_hash")) == "":
                _page_owner_first_setup(owner_row)
                return

    # 3) 一般登入
    _page_normal_login()
