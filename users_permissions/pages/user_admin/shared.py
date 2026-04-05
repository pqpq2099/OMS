from __future__ import annotations

import streamlit as st

from users_permissions.logic.user_permission import ROLE_LABELS
from users_permissions.logic.user_query import UserAdminContext, build_user_admin_context as build_user_admin_context_logic
from ui_text import t


def render_section_title(title_key: str, caption_key: str | None = None) -> None:
    st.subheader(t(title_key))
    if caption_key:
        st.caption(t(caption_key))


def build_user_admin_context() -> UserAdminContext:
    return build_user_admin_context_logic(
        current_user_role_id=str(st.session_state.get("login_role_id", "")).strip().lower(),
        current_user_id=str(st.session_state.get("login_user", "")).strip(),
        role_labels=ROLE_LABELS,
    )


