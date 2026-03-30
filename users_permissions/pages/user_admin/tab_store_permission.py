from __future__ import annotations

import streamlit as st

from users_permissions.logic.user_permission import is_leader_role, is_store_manager_role
from users_permissions.logic.logic_user_admin import (
    build_store_permission_display_df,
    build_store_permission_panel,
    build_store_permission_selected_state,
    build_store_reassign_form_state,
    submit_store_reassign,
)
from users_permissions.services.service_users import UserServiceError
from ui_text import t


def render_tab_store_permission(ctx):
    st.subheader(t("store_permission_management"))
    c1, c2 = st.columns(2)

    with c1:
        st.markdown(f"#### {t('manager_management')}")
        manager_df, manager_option_map, store_names_only = build_store_permission_panel(ctx, is_store_manager_role)
        if manager_df.empty:
            st.info(t("no_manager_data"))
        else:
            show_manager_df = build_store_permission_display_df(manager_df)
            show_manager_df.columns = [t("manager_account"), t("manager_name"), t("manager_store"), t("status")]
            st.dataframe(show_manager_df, use_container_width=True, hide_index=True)
            manager_labels = list(manager_option_map.keys())
            selected_manager_label = st.selectbox(t("select_manager"), manager_labels, key="mgr_user_select")
            selected_manager_user_id = manager_option_map.get(selected_manager_label, "")
            manager_state = build_store_permission_selected_state(ctx, manager_df, selected_manager_user_id)
            selected_manager_user_id = manager_state["selected_user_id"]
            selected_manager_store_name = st.selectbox(t("reassign_store"), manager_state["store_names_only"], index=manager_state["store_idx"], key="mgr_store_scope_select")
            if st.button(t("update_manager_store"), use_container_width=True, key="btn_update_manager_scope"):
                try:
                    submit_store_reassign(
                        ctx,
                        **build_store_reassign_form_state(
                            ctx,
                            manager_state,
                            selected_manager_store_name,
                            action="reassign_store_manager",
                            note="Reassign store manager store",
                        ),
                    )
                    st.success(t("manager_store_updated"))
                    st.rerun()
                except UserServiceError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"{t('update_failed')}：{e}")

    with c2:
        st.markdown(f"#### {t('leader_management')}")
        leader_df, leader_option_map, store_names_only = build_store_permission_panel(ctx, is_leader_role)
        if leader_df.empty:
            st.info(t("no_leader_data"))
        else:
            show_leader_df = build_store_permission_display_df(leader_df)
            show_leader_df.columns = [t("leader_account"), t("leader_name"), t("manager_store"), t("status")]
            st.dataframe(show_leader_df, use_container_width=True, hide_index=True)
            leader_labels = list(leader_option_map.keys())
            selected_leader_label = st.selectbox(t("select_leader"), leader_labels, key="leader_user_select")
            selected_leader_user_id = leader_option_map.get(selected_leader_label, "")
            leader_state = build_store_permission_selected_state(ctx, leader_df, selected_leader_user_id)
            selected_leader_user_id = leader_state["selected_user_id"]
            selected_leader_store_name = st.selectbox(t("reassign_store"), leader_state["store_names_only"], index=leader_state["store_idx"], key="leader_store_scope_select")
            if st.button(t("update_leader_store"), use_container_width=True, key="btn_update_leader_scope"):
                try:
                    submit_store_reassign(
                        ctx,
                        **build_store_reassign_form_state(
                            ctx,
                            leader_state,
                            selected_leader_store_name,
                            action="reassign_leader",
                            note="Reassign leader store",
                        ),
                    )
                    st.success(t("leader_store_updated"))
                    st.rerun()
                except UserServiceError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"{t('update_failed')}：{e}")
