from __future__ import annotations

from users_permissions.logic.user_write import (
    force_change_user_password,
    initialize_owner,
    login,
)
from users_permissions.services.service_users import get_owner_first_setup_row


def get_owner_first_setup_state():
    return get_owner_first_setup_row()


def submit_login(account: str, password: str):
    return login(account, password)


def submit_owner_initialize(user_id: str, new_password: str, confirm_password: str):
    return initialize_owner(user_id, new_password, confirm_password)


def submit_force_change_password(user_id: str, new_password: str, confirm_password: str):
    return force_change_user_password(user_id, new_password, confirm_password)


def resolve_login_page_state(*, has_login_user: bool, force_change_password: bool):
    if has_login_user and force_change_password:
        return "force_change_password", None
    owner_row = get_owner_first_setup_state()
    if owner_row is not None:
        return "owner_first_setup", owner_row
    return "normal_login", None



def preload_login_users():
    return None


def build_login_page_view_state(*, has_login_user: bool, force_change_password: bool):
    page_state, owner_row = resolve_login_page_state(has_login_user=has_login_user, force_change_password=force_change_password)
    return {"page_state": page_state, "owner_row": owner_row}
