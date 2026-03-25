from __future__ import annotations

import streamlit as st

from users_permissions.services.service_users import (
    change_own_password,
    create_user_account,
    force_change_password,
    initialize_owner_password,
    login_user,
    now_ts,
    reset_user_password_admin,
    toggle_user_active_admin,
    update_user_profile,
)


def create_user(data: dict):
    return create_user_account(data, actor_user_id=st.session_state.get("login_user", ""))


def update_user(user_id: str, data: dict, action: str = "update_user", note: str = "Update user profile"):
    return update_user_profile(
        user_id,
        data.get("updates", {}),
        before=data.get("before", {}),
        after=data.get("after", {}),
        action=action,
        note=note,
        actor_user_id=st.session_state.get("login_user", ""),
    )


def reset_user_password(user_id: str, target_row: dict):
    return reset_user_password_admin(user_id, target_row, actor_user_id=st.session_state.get("login_user", ""))


def toggle_user_active(user_id: str, target_row: dict, target_next_active: int):
    return toggle_user_active_admin(user_id, target_row, target_next_active, actor_user_id=st.session_state.get("login_user", ""))



def login(account: str, password: str):
    return login_user(account, password)


def initialize_owner(user_id: str, new_password: str, confirm_password: str):
    return initialize_owner_password(user_id, new_password, confirm_password)


def force_change_user_password(user_id: str, new_password: str, confirm_password: str):
    return force_change_password(user_id, new_password, confirm_password)


def change_my_password(user_id: str, *, current_password: str, new_password: str, confirm_password: str):
    return change_own_password(
        user_id,
        current_password=current_password,
        new_password=new_password,
        confirm_password=confirm_password,
    )
