from __future__ import annotations

import streamlit as st

from users_permissions.logic.logic_user_admin import (
    build_user_list_table,
    build_user_quick_manage_display,
    build_user_quick_manage_state,
    submit_reset_password,
    submit_toggle_user_active,
)
from users_permissions.services.service_users import UserServiceError
from ui_text import t


def render_tab_user_list(ctx):
    st.subheader(t("user_list"))
    if ctx.users_view.empty:
        st.info(t("no_user_data"))
    else:
        show_df = build_user_list_table(ctx.users_view).copy()
        show_df.columns = [t("account"), t("name"), t("role"), t("store"), t("status"), t("last_login")]
        st.dataframe(show_df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader(t("quick_manage"))
    quick_state = build_user_quick_manage_state(ctx, "")
    managed_target_df = quick_state["managed_target_df"]
    if managed_target_df.empty:
        st.info(t("no_manageable_users"))
        return

    user_labels = list(quick_state["user_option_map"].keys())
    selected_user_label = st.selectbox(t("select_user"), user_labels, key="ua_quick_selected_user")
    selected_user_id = quick_state["user_option_map"].get(selected_user_label, "")
    selected_state = build_user_quick_manage_state(ctx, selected_user_id)
    target_row = selected_state["target_row"]
    target_user = selected_state["target_user"]
    selected_user_id = selected_state["selected_user_id"]
    quick_display = build_user_quick_manage_display(selected_state, {"disable": t("disable_account"), "enable": t("enable_account")})

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button(t("reset_password_123456"), use_container_width=True, key="btn_reset_password"):
            try:
                submit_reset_password(ctx, user_id=selected_user_id, target_user=target_user, target_row=target_row.to_dict())
                st.success(t("reset_password_success"))
                st.rerun()
            except UserServiceError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"{t('action_failed')}：{e}")
    with c2:
        target_next_active = selected_state["target_next_active"]
        if st.button(quick_display["target_label"], use_container_width=True, key="btn_toggle_user_active"):
            try:
                submit_toggle_user_active(ctx, user_id=selected_user_id, target_user=target_user, target_row=target_row.to_dict(), target_next_active=target_next_active)
                st.success(t("account_status_updated"))
                st.rerun()
            except UserServiceError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"{t('update_failed')}：{e}")
    with c3:
        st.caption(t("current_status"))
        st.write(f"{t('role')}：{quick_display['role_text']}")
        st.write(f"{t('store')}：{quick_display['store_text']}")
        st.write(f"{t('status')}：{quick_display['status_text']}")
