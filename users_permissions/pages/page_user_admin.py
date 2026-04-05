from __future__ import annotations

import streamlit as st

from shared.utils.permissions import require_permission
from users_permissions.pages.user_admin.shared import build_user_admin_context
from users_permissions.pages.user_admin.tab_account_edit import render_tab_account_edit
from users_permissions.pages.user_admin.tab_promotion import render_tab_promotion
from users_permissions.pages.user_admin.tab_role_permission import render_tab_role_permission
from users_permissions.pages.user_admin.tab_store_permission import render_tab_store_permission
from users_permissions.pages.user_admin.tab_user_list import render_tab_user_list
from ui_text import t


def page_user_admin():
    st.title(f"👥 {t('title_user_admin')}")

    if not require_permission("user.account.manage"):
        return
    ctx = build_user_admin_context()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        t("tab_user_list"),
        t("tab_account_edit"),
        t("tab_store_permission"),
        t("tab_promotion"),
        t("tab_role_permission"),
    ])

    with tab1:
        render_tab_user_list(ctx)

    with tab2:
        render_tab_account_edit(ctx)

    with tab3:
        render_tab_store_permission(ctx)

    with tab4:
        render_tab_promotion(ctx)

    with tab5:
        render_tab_role_permission(ctx)
