# ============================================================
# ORIVIA OMS
# 檔案：pages/page_account_settings.py
# 說明：個人帳號管理頁
# 功能：顯示目前登入者資訊、允許使用者自行修改密碼。
# 注意：這一頁只處理本人帳號，不處理他人帳號管理。
# ============================================================

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib

import pandas as pd
import streamlit as st

from oms_core import get_header, get_spreadsheet, read_table, update_sheet_row_by_key


# ============================================================
# [A] 基本工具
# ============================================================
def _now_ts() -> str:
    return datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d %H:%M:%S")


def _norm_text(value) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _sha256(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _load_users_df() -> pd.DataFrame:
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
        "updated_at",
        "updated_by",
    ]:
        if col not in df.columns:
            df[col] = ""
    return df


def _update_user_fields(user_id: str, updates: dict):
    return update_sheet_row_by_key(
        sheet_name="users",
        key_field="user_id",
        key_value=user_id,
        updates=updates,
    )


def _append_audit_log(action: str, entity_id: str, note: str):
    try:
        sh = get_spreadsheet()
        if sh is None:
            return
        ws = sh.worksheet("audit_logs")
        header = get_header("audit_logs")
        row = {c: "" for c in header}
        row.update(
            {
                "audit_id": f"AUDIT_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                "ts": _now_ts(),
                "user_id": _norm_text(st.session_state.get("login_user", "")) or "SYSTEM",
                "action": action,
                "table_name": "users",
                "entity_id": entity_id,
                "before_json": "{}",
                "after_json": "{}",
                "note": note,
            }
        )
        ws.append_row([row.get(c, "") for c in header], value_input_option="USER_ENTERED")
    except Exception:
        return


def _role_label(role_id: str) -> str:
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
    return mapping.get(rid, rid or "-")


# ============================================================
# [B] 頁面主體
# ============================================================
def page_account_settings():
    st.title("🙍 個人帳號管理")

    login_user_id = _norm_text(st.session_state.get("login_user", ""))
    if not login_user_id:
        st.warning("請先登入。")
        return

    users_df = _load_users_df()
    if users_df.empty:
        st.error("users 表讀取失敗")
        return

    work = users_df.copy()
    work["user_id"] = work["user_id"].apply(_norm_text)
    user_hit = work[work["user_id"] == login_user_id].copy()
    if user_hit.empty:
        st.error("找不到目前登入者資料")
        return

    user_row = user_hit.iloc[0]

    info_df = pd.DataFrame(
        [
            {"欄位": "帳號", "內容": _norm_text(user_row.get("account_code")) or "-"},
            {"欄位": "姓名", "內容": _norm_text(user_row.get("display_name")) or "-"},
            {"欄位": "角色", "內容": _role_label(user_row.get("role_id"))},
            {"欄位": "分店範圍", "內容": _norm_text(user_row.get("store_scope")) or "-"},
            {"欄位": "Email", "內容": _norm_text(user_row.get("email")) or "-"},
        ]
    )

    st.markdown("### 目前帳號資訊")
    st.table(info_df)

    st.markdown("### 修改自己的密碼")
    st.caption("密碼至少 6 碼。修改成功後，下次登入會直接使用新密碼。")

    with st.form("account_change_password_form"):
        current_password = st.text_input("目前密碼", type="password")
        new_password = st.text_input("新密碼", type="password")
        confirm_password = st.text_input("確認新密碼", type="password")
        submitted = st.form_submit_button("儲存新密碼", use_container_width=True)

        if submitted:
            current_hash = _norm_text(user_row.get("password_hash"))

            if not current_password or not new_password or not confirm_password:
                st.error("請完整輸入目前密碼、新密碼、確認密碼。")
                return

            if current_hash != _sha256(current_password):
                st.error("目前密碼不正確。")
                return

            if len(new_password) < 6:
                st.error("新密碼至少需要 6 碼。")
                return

            if new_password != confirm_password:
                st.error("新密碼與確認密碼不一致。")
                return

            if current_password == new_password:
                st.error("新密碼不可與目前密碼相同。")
                return

            try:
                _update_user_fields(
                    login_user_id,
                    {
                        "password_hash": _sha256(new_password),
                        "must_change_password": 0,
                        "updated_at": _now_ts(),
                        "updated_by": login_user_id,
                    },
                )
                _append_audit_log(
                    action="self_change_password",
                    entity_id=login_user_id,
                    note="使用者於個人帳號管理頁自行修改密碼",
                )
                st.success("✅ 密碼已更新")
            except Exception as e:
                st.error(f"修改失敗：{e}")
