from __future__ import annotations

import streamlit as st

from users_permissions.logic.user_query import norm_text
from users_permissions.logic.logic_user_admin import (
    build_account_edit_create_state,
    build_account_edit_selected_state,
    build_account_edit_submit_payload,
    build_account_edit_user_options,
    resolve_create_user_store_label,
    submit_create_user,
    submit_update_user,
)
from users_permissions.services.service_users import UserServiceError
from ui_text import t


def render_tab_account_edit(ctx):
    st.subheader(t("add_user"))
    create_state = build_account_edit_create_state(ctx)
    role_options = create_state["role_options"]
    store_option_map = create_state["store_option_map"]
    store_options = create_state["store_options"]

    if not role_options:
        st.warning(t("no_available_roles"))
    else:
        with st.form("form_create_user", clear_on_submit=True):
            new_account_code = st.text_input(t("login_account"), placeholder=t("placeholder_account")).strip()
            new_display_name = st.text_input(t("display_name"), placeholder=t("placeholder_name")).strip()
            selected_role_name = st.selectbox(t("role_name"), options=role_options, index=0)
            selected_role_id = ctx.role_name_to_id[selected_role_name]
            st.session_state["create_user_store_label"] = resolve_create_user_store_label(
                store_options,
                st.session_state.get("create_user_store_label", ""),
                selected_role_id,
                t("all_stores"),
            )
            selected_store_label = st.selectbox(t("store_name"), options=store_options, key="create_user_store_label")
            selected_store_scope = store_option_map[selected_store_label]
            st.caption(t("default_password"))
            st.caption(t("change_password_first_login"))
            submitted_create = st.form_submit_button(t("create_user_button"), use_container_width=True)

        if submitted_create:
            try:
                submit_create_user(
                    ctx,
                    account_code=new_account_code,
                    display_name=new_display_name,
                    role_id=selected_role_id,
                    store_scope=selected_store_scope,
                )
                st.success(t("create_success"))
                if "create_user_store_label" in st.session_state:
                    del st.session_state["create_user_store_label"]
                st.rerun()
            except UserServiceError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"{t('create_failed')}：{e}")

    st.divider()
    st.subheader(t("edit_existing_user"))
    edit_state = build_account_edit_user_options(ctx)
    editable_users_df = edit_state["editable_users_df"]
    if editable_users_df.empty:
        st.info(t("no_editable_users"))
        return

    selected_edit_label = st.selectbox(t("select_edit_user"), edit_state["edit_user_labels"], key="ua_edit_selected_user")
    selected_edit_user_id = edit_state["edit_user_option_map"].get(selected_edit_label, "")
    selected_state = build_account_edit_selected_state(ctx, selected_edit_user_id)
    edit_row = selected_state["edit_row"]
    target_user = selected_state["target_user"]
    edit_role_names = selected_state["edit_role_names"]
    edit_role_index = selected_state["edit_role_index"]
    edit_store_option_map = selected_state["edit_store_option_map"]
    edit_store_names = selected_state["edit_store_names"]
    edit_store_index = selected_state["edit_store_index"]

    with st.form("form_edit_user"):
        edit_display_name = st.text_input(t("name"), value=norm_text(edit_row.get("display_name")), key="edit_display_name")
        edit_role_name = st.selectbox(t("role_name"), edit_role_names, index=edit_role_index, key="edit_role_name")
        edit_store_name = st.selectbox(t("store_name"), edit_store_names, index=edit_store_index, key="edit_store_name")
        edit_is_active = st.selectbox(t("status"), options=[t("active"), t("inactive")], index=0 if int(edit_row.get("is_active", 1)) == 1 else 1, key="edit_is_active")
        submitted_edit = st.form_submit_button(t("edit_user_button"), use_container_width=True)

    if submitted_edit:
        submit_payload = build_account_edit_submit_payload(
            ctx,
            edit_row,
            edit_display_name,
            edit_role_name,
            edit_store_name,
            edit_is_active,
            t("active"),
        )
        try:
            submit_update_user(
                ctx,
                user_id=selected_edit_user_id,
                target_user=target_user,
                updates=submit_payload["updates"],
                before=submit_payload["before"],
                after=submit_payload["after"],
                action="update_user",
                note="Admin edited user profile",
            )
            st.success(t("user_updated"))
            st.rerun()
        except UserServiceError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"{t('update_failed')}：{e}")
