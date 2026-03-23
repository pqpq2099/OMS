from __future__ import annotations

from datetime import datetime
import hashlib
import streamlit as st

from operations.logic.user_query import clear_user_admin_tables_cache, load_users_df, norm_text
from services.service_audit import audit_log
from services.service_id import allocate_user_id
from services.service_sheet import sheet_append, sheet_bust_cache, sheet_get_header, sheet_update


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def update_user_fields_by_user_id(user_id: str, updates: dict):
    users_df = load_users_df()
    if users_df.empty:
        raise ValueError("users table is empty")

    mask = users_df["user_id"].astype(str).str.strip() == str(user_id).strip()
    if not mask.any():
        raise ValueError(f"user_id not found: {user_id}")

    normalized_updates = {}
    for field, value in updates.items():
        normalized_updates[field] = value

    sheet_update("users", "user_id", user_id, normalized_updates)
    clear_user_admin_tables_cache()


def create_user(data: dict):
    new_user_id = allocate_user_id()
    now_value = now_ts()
    new_row = {
        "user_id": new_user_id,
        "account_code": data["account_code"].strip(),
        "email": "",
        "display_name": data["display_name"].strip(),
        "password_hash": hash_password("123456"),
        "must_change_password": 1,
        "role_id": data["role_id"],
        "store_scope": data["store_scope"],
        "is_active": 1,
        "last_login_at": "",
        "created_at": now_value,
        "created_by": st.session_state.get("login_user", ""),
        "updated_at": now_value,
        "updated_by": st.session_state.get("login_user", ""),
    }
    users_header = sheet_get_header("users")
    sheet_append("users", users_header, [new_row])
    audit_log(
        action="create_user",
        entity_id=new_user_id,
        before=None,
        after={
            "account_code": data["account_code"].strip(),
            "display_name": data["display_name"].strip(),
            "role_id": data["role_id"],
            "store_scope": data["store_scope"],
        },
        note="Create new user",
    )
    sheet_bust_cache()
    return new_user_id


def update_user(user_id: str, data: dict, action: str = "update_user", note: str = "Update user profile"):
    before = data.get("before", {})
    updates = data.get("updates", {})
    after = data.get("after", {})
    update_user_fields_by_user_id(user_id, updates)
    audit_log(action=action, entity_id=user_id, before=before, after=after, note=note)
    return user_id


def reset_user_password(user_id: str, target_row: dict):
    before = {
        "user_id": user_id,
        "account_code": norm_text(target_row.get("account_code")),
        "must_change_password": norm_text(target_row.get("must_change_password")),
    }
    update_user(
        user_id,
        {
            "before": before,
            "after": {"must_change_password": 1},
            "updates": {
                "password_hash": hash_password("123456"),
                "must_change_password": 1,
                "updated_at": now_ts(),
                "updated_by": st.session_state.get("login_user", ""),
            },
        },
        action="reset_password",
        note="Reset password to default 123456",
    )


def toggle_user_active(user_id: str, target_row: dict, target_next_active: int):
    before = {"user_id": user_id, "is_active": int(target_row.get("is_active", 1))}
    update_user(
        user_id,
        {
            "before": before,
            "after": {"is_active": target_next_active},
            "updates": {
                "is_active": target_next_active,
                "updated_at": now_ts(),
                "updated_by": st.session_state.get("login_user", ""),
            },
        },
        action="toggle_user_active",
        note="Adjust user active status",
    )
