from __future__ import annotations

import pandas as pd
import streamlit as st

from operations.logic.user_permission import (
    PROMOTION_ROLE_ORDER,
    ROLE_LABELS,
    ROLE_PERMISSION_ROWS,
    can_access_user_admin,
    can_assign_role,
    can_edit_user,
    count_active_store_managers,
    is_admin_role,
    is_leader_role,
    is_promotion_target_role,
    is_store_manager_role,
    requires_specific_store_scope,
)
from operations.logic.user_query import (
    build_role_maps,
    build_store_maps,
    build_store_option_map,
    build_users_view,
    get_store_label_by_scope,
    load_roles_df,
    load_stores_df,
    load_users_df,
    norm_text,
    user_display_label,
)
from operations.logic.user_write import (
    create_user,
    now_ts,
    reset_user_password,
    toggle_user_active,
    update_user,
)
from ui_text import t


def page_user_admin():
    st.title(f"👥 {t('title_user_admin')}")

    current_user = {
        "role_id": str(st.session_state.get("login_role_id", "")).strip().lower(),
        "user_id": str(st.session_state.get("login_user", "")).strip(),
    }
    if not can_access_user_admin(current_user["role_id"]):
        st.error(t("no_access_user_admin"))
        return

    users_df = load_users_df()
    roles_df = load_roles_df()
    stores_df = load_stores_df()

    managed_users_df = users_df[users_df["role_id"] != "owner"].copy().reset_index(drop=True)
    users_view = build_users_view(managed_users_df, roles_df, stores_df, ROLE_LABELS)
    store_id_to_name, store_name_to_id = build_store_maps(stores_df)
    role_id_to_name, role_name_to_id = build_role_maps(roles_df, ROLE_LABELS, current_user["role_id"])

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        t("tab_user_list"),
        t("tab_account_edit"),
        t("tab_store_permission"),
        t("tab_promotion"),
        t("tab_role_permission"),
    ])

    with tab1:
        st.subheader(t("user_list"))
        if users_view.empty:
            st.info(t("no_user_data"))
        else:
            show_df = users_view[["account_code", "display_name", "role_display", "store_display", "status_display", "last_login_at"]].copy()
            show_df.columns = [t("account"), t("name"), t("role"), t("store"), t("status"), t("last_login")]
            st.dataframe(show_df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader(t("quick_manage"))
        managed_target_df = users_view.sort_values(["display_name", "account_code"]).copy()
        if managed_target_df.empty:
            st.info(t("no_manageable_users"))
        else:
            user_option_map = {user_display_label(row, store_id_to_name, ROLE_LABELS): row["user_id"] for _, row in managed_target_df.iterrows()}
            user_labels = list(user_option_map.keys())
            selected_user_label = st.selectbox(t("select_user"), user_labels, key="ua_quick_selected_user")
            selected_user_id = user_option_map.get(selected_user_label, "")
            target_row = managed_target_df[managed_target_df["user_id"] == selected_user_id].iloc[0]
            target_user = {"role_id": norm_text(target_row.get("role_id")), "user_id": selected_user_id}

            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button(t("reset_password_123456"), use_container_width=True, key="btn_reset_password"):
                    if can_edit_user(current_user, target_user):
                        try:
                            reset_user_password(selected_user_id, target_row.to_dict())
                            st.success(t("reset_password_success"))
                            st.rerun()
                        except Exception as e:
                            st.error(f"{t('action_failed')}：{e}")
            with c2:
                target_next_active = 0 if int(target_row.get("is_active", 1)) == 1 else 1
                target_label = t("disable_account") if target_next_active == 0 else t("enable_account")
                if st.button(target_label, use_container_width=True, key="btn_toggle_user_active"):
                    if can_edit_user(current_user, target_user):
                        try:
                            toggle_user_active(selected_user_id, target_row.to_dict(), target_next_active)
                            st.success(t("account_status_updated"))
                            st.rerun()
                        except Exception as e:
                            st.error(f"{t('update_failed')}：{e}")
            with c3:
                st.caption(t("current_status"))
                st.write(f"{t('role')}：{norm_text(target_row.get('role_display'))}")
                st.write(f"{t('store')}：{norm_text(target_row.get('store_display'))}")
                st.write(f"{t('status')}：{norm_text(target_row.get('status_display'))}")

    with tab2:
        st.subheader(t("add_user"))
        create_users_df = users_df.copy()
        role_options = list(role_name_to_id.keys())
        store_option_map = build_store_option_map(store_id_to_name)
        store_options = list(store_option_map.keys())

        if not role_options:
            st.warning(t("no_available_roles"))
        else:
            if "create_user_store_label" not in st.session_state or st.session_state["create_user_store_label"] not in store_options:
                if t("all_stores") in store_options:
                    default_non_admin_label = next((x for x in store_options if x != t("all_stores")), t("all_stores"))
                else:
                    default_non_admin_label = store_options[0] if store_options else ""
                st.session_state["create_user_store_label"] = default_non_admin_label

            with st.form("form_create_user", clear_on_submit=True):
                new_account_code = st.text_input(t("login_account"), placeholder=t("placeholder_account")).strip()
                new_display_name = st.text_input(t("display_name"), placeholder=t("placeholder_name")).strip()
                selected_role_name = st.selectbox(t("role_name"), options=role_options, index=0)
                selected_role_id = role_name_to_id[selected_role_name]

                if is_admin_role(selected_role_id):
                    if t("all_stores") in store_options:
                        st.session_state["create_user_store_label"] = t("all_stores")
                else:
                    if st.session_state.get("create_user_store_label") == t("all_stores"):
                        non_all_options = [x for x in store_options if x != t("all_stores")]
                        st.session_state["create_user_store_label"] = non_all_options[0] if non_all_options else (store_options[0] if store_options else "")

                selected_store_label = st.selectbox(t("store_name"), options=store_options, key="create_user_store_label")
                selected_store_scope = store_option_map[selected_store_label]
                st.caption(t("default_password"))
                st.caption(t("change_password_first_login"))
                submitted_create = st.form_submit_button(t("create_user_button"), use_container_width=True)

            if submitted_create:
                work_users = create_users_df.copy()
                work_users["account_code"] = work_users["account_code"].astype(str).str.strip().str.lower()
                account_exists = new_account_code.strip().lower() in work_users["account_code"].tolist()

                if not new_account_code:
                    st.error(t("please_enter_account"))
                elif not new_display_name:
                    st.error(t("please_enter_name"))
                elif account_exists:
                    st.error(t("account_exists"))
                elif not can_assign_role(current_user, selected_role_id):
                    st.error(t("no_access_user_admin"))
                elif requires_specific_store_scope(selected_role_id) and selected_store_scope == "ALL":
                    st.error(t("role_requires_store"))
                elif is_store_manager_role(selected_role_id) and count_active_store_managers(users_df, selected_store_scope) >= 3:
                    st.error(t("store_manager_limit_reached_create"))
                else:
                    try:
                        create_user({"account_code": new_account_code, "display_name": new_display_name, "role_id": selected_role_id, "store_scope": selected_store_scope})
                        st.success(t("create_success"))
                        if "create_user_store_label" in st.session_state:
                            del st.session_state["create_user_store_label"]
                        st.rerun()
                    except Exception as e:
                        st.error(f"{t('create_failed')}：{e}")

        st.divider()
        st.subheader(t("edit_existing_user"))
        editable_users_df = users_view.sort_values(["display_name", "account_code"]).copy()
        if editable_users_df.empty:
            st.info(t("no_editable_users"))
        else:
            edit_user_option_map = {user_display_label(row, store_id_to_name, ROLE_LABELS): row["user_id"] for _, row in editable_users_df.iterrows()}
            edit_user_labels = list(edit_user_option_map.keys())
            selected_edit_label = st.selectbox(t("select_edit_user"), edit_user_labels, key="ua_edit_selected_user")
            selected_edit_user_id = edit_user_option_map.get(selected_edit_label, "")
            edit_row = editable_users_df[editable_users_df["user_id"] == selected_edit_user_id].iloc[0]
            target_user = {"role_id": norm_text(edit_row.get("role_id")), "user_id": selected_edit_user_id}

            edit_role_names = list(role_name_to_id.keys())
            current_role_name = role_id_to_name.get(norm_text(edit_row.get("role_id")), norm_text(edit_row.get("role_id")))
            edit_role_index = edit_role_names.index(current_role_name) if current_role_name in edit_role_names else 0
            edit_store_option_map = build_store_option_map(store_id_to_name)
            edit_store_names = list(edit_store_option_map.keys())
            current_store_label = get_store_label_by_scope(edit_store_option_map, norm_text(edit_row.get("store_scope")))
            if current_store_label not in edit_store_names:
                current_store_label = edit_store_names[0]
            edit_store_index = edit_store_names.index(current_store_label)

            with st.form("form_edit_user"):
                edit_display_name = st.text_input(t("name"), value=norm_text(edit_row.get("display_name")), key="edit_display_name")
                edit_role_name = st.selectbox(t("role_name"), edit_role_names, index=edit_role_index, key="edit_role_name")
                edit_store_name = st.selectbox(t("store_name"), edit_store_names, index=edit_store_index, key="edit_store_name")
                edit_is_active = st.selectbox(t("status"), options=[t("active"), t("inactive")], index=0 if int(edit_row.get("is_active", 1)) == 1 else 1, key="edit_is_active")
                submitted_edit = st.form_submit_button(t("edit_user_button"), use_container_width=True)

            if submitted_edit:
                new_role_id = role_name_to_id[edit_role_name]
                new_store_scope = edit_store_option_map[edit_store_name]
                new_is_active = 1 if edit_is_active == t("active") else 0
                if not can_edit_user(current_user, target_user):
                    st.error(t("no_access_user_admin"))
                elif not can_assign_role(current_user, new_role_id):
                    st.error(t("no_access_user_admin"))
                elif requires_specific_store_scope(new_role_id) and new_store_scope == "ALL":
                    st.error(t("role_requires_store"))
                elif is_store_manager_role(new_role_id) and count_active_store_managers(users_df, new_store_scope, exclude_user_id=selected_edit_user_id) >= 3:
                    st.error(t("store_manager_limit_reached_update"))
                else:
                    before = {
                        "display_name": norm_text(edit_row.get("display_name")),
                        "role_id": norm_text(edit_row.get("role_id")),
                        "store_scope": norm_text(edit_row.get("store_scope")),
                        "is_active": int(edit_row.get("is_active", 1)),
                    }
                    after = {
                        "display_name": edit_display_name.strip(),
                        "role_id": new_role_id,
                        "store_scope": new_store_scope,
                        "is_active": new_is_active,
                    }
                    try:
                        update_user(
                            selected_edit_user_id,
                            {
                                "before": before,
                                "after": after,
                                "updates": {
                                    "display_name": edit_display_name.strip(),
                                    "role_id": new_role_id,
                                    "store_scope": new_store_scope,
                                    "is_active": new_is_active,
                                    "updated_at": now_ts(),
                                    "updated_by": st.session_state.get("login_user", ""),
                                },
                            },
                            action="update_user",
                            note="Admin edited user profile",
                        )
                        st.success(t("user_updated"))
                        st.rerun()
                    except Exception as e:
                        st.error(f"{t('update_failed')}：{e}")

    with tab3:
        st.subheader(t("store_permission_management"))
        c1, c2 = st.columns(2)

        with c1:
            st.markdown(f"#### {t('manager_management')}")
            manager_df = users_view[users_view["role_id"].apply(is_store_manager_role)].copy()
            if manager_df.empty:
                st.info(t("no_manager_data"))
            else:
                show_manager_df = manager_df[["account_code", "display_name", "store_display", "status_display"]].copy()
                show_manager_df.columns = [t("manager_account"), t("manager_name"), t("manager_store"), t("status")]
                st.dataframe(show_manager_df, use_container_width=True, hide_index=True)
                manager_option_map = {user_display_label(row, store_id_to_name, ROLE_LABELS): row["user_id"] for _, row in manager_df.sort_values(["display_name", "account_code"]).iterrows()}
                manager_labels = list(manager_option_map.keys())
                selected_manager_label = st.selectbox(t("select_manager"), manager_labels, key="mgr_user_select")
                selected_manager_user_id = manager_option_map.get(selected_manager_label, "")
                manager_row = manager_df[manager_df["user_id"] == selected_manager_user_id].iloc[0]
                target_user = {"role_id": norm_text(manager_row.get("role_id")), "user_id": selected_manager_user_id}
                store_names_only = [name for name, sid in store_name_to_id.items() if sid != "ALL"]
                current_manager_store_name = store_id_to_name.get(norm_text(manager_row.get("store_scope")), store_names_only[0])
                if current_manager_store_name not in store_names_only:
                    current_manager_store_name = store_names_only[0]
                manager_store_idx = store_names_only.index(current_manager_store_name)
                selected_manager_store_name = st.selectbox(t("reassign_store"), store_names_only, index=manager_store_idx, key="mgr_store_scope_select")
                new_manager_store_scope = store_name_to_id[selected_manager_store_name]
                if st.button(t("update_manager_store"), use_container_width=True, key="btn_update_manager_scope"):
                    if not can_edit_user(current_user, target_user):
                        st.error(t("no_access_user_admin"))
                    elif count_active_store_managers(users_df, new_manager_store_scope, exclude_user_id=selected_manager_user_id) >= 3:
                        st.error(t("store_manager_limit_assign"))
                    else:
                        before = {"store_scope": norm_text(manager_row.get("store_scope"))}
                        after = {"store_scope": new_manager_store_scope}
                        try:
                            update_user(
                                selected_manager_user_id,
                                {
                                    "before": before,
                                    "after": after,
                                    "updates": {
                                        "store_scope": new_manager_store_scope,
                                        "updated_at": now_ts(),
                                        "updated_by": st.session_state.get("login_user", ""),
                                    },
                                },
                                action="reassign_store_manager",
                                note="Reassign store manager store",
                            )
                            st.success(t("manager_store_updated"))
                            st.rerun()
                        except Exception as e:
                            st.error(f"{t('update_failed')}：{e}")

        with c2:
            st.markdown(f"#### {t('leader_management')}")
            leader_df = users_view[users_view["role_id"].apply(is_leader_role)].copy()
            if leader_df.empty:
                st.info(t("no_leader_data"))
            else:
                show_leader_df = leader_df[["account_code", "display_name", "store_display", "status_display"]].copy()
                show_leader_df.columns = [t("leader_account"), t("leader_name"), t("manager_store"), t("status")]
                st.dataframe(show_leader_df, use_container_width=True, hide_index=True)
                leader_option_map = {user_display_label(row, store_id_to_name, ROLE_LABELS): row["user_id"] for _, row in leader_df.sort_values(["display_name", "account_code"]).iterrows()}
                leader_labels = list(leader_option_map.keys())
                selected_leader_label = st.selectbox(t("select_leader"), leader_labels, key="leader_user_select")
                selected_leader_user_id = leader_option_map.get(selected_leader_label, "")
                leader_row = leader_df[leader_df["user_id"] == selected_leader_user_id].iloc[0]
                target_user = {"role_id": norm_text(leader_row.get("role_id")), "user_id": selected_leader_user_id}
                store_names_only = [name for name, sid in store_name_to_id.items() if sid != "ALL"]
                current_leader_store_name = store_id_to_name.get(norm_text(leader_row.get("store_scope")), store_names_only[0])
                if current_leader_store_name not in store_names_only:
                    current_leader_store_name = store_names_only[0]
                leader_store_idx = store_names_only.index(current_leader_store_name)
                selected_leader_store_name = st.selectbox(t("reassign_store"), store_names_only, index=leader_store_idx, key="leader_store_scope_select")
                new_leader_store_scope = store_name_to_id[selected_leader_store_name]
                if st.button(t("update_leader_store"), use_container_width=True, key="btn_update_leader_scope"):
                    if not can_edit_user(current_user, target_user):
                        st.error(t("no_access_user_admin"))
                    else:
                        before = {"store_scope": norm_text(leader_row.get("store_scope"))}
                        after = {"store_scope": new_leader_store_scope}
                        try:
                            update_user(
                                selected_leader_user_id,
                                {
                                    "before": before,
                                    "after": after,
                                    "updates": {
                                        "store_scope": new_leader_store_scope,
                                        "updated_at": now_ts(),
                                        "updated_by": st.session_state.get("login_user", ""),
                                    },
                                },
                                action="reassign_leader",
                                note="Reassign leader store",
                            )
                            st.success(t("leader_store_updated"))
                            st.rerun()
                        except Exception as e:
                            st.error(f"{t('update_failed')}：{e}")

    with tab4:
        st.subheader(t("promotion_title"))
        st.caption(t("promotion_caption"))
        promotion_users_df = users_view[users_view["role_id"].apply(is_promotion_target_role)].copy()
        if promotion_users_df.empty:
            st.info(t("no_promotion_target"))
        else:
            promotion_user_option_map = {user_display_label(row, store_id_to_name, ROLE_LABELS): row["user_id"] for _, row in promotion_users_df.sort_values(["display_name", "account_code"]).iterrows()}
            promotion_labels = list(promotion_user_option_map.keys())
            selected_promotion_label = st.selectbox(t("select_employee"), promotion_labels, key="promotion_target_user")
            selected_promotion_user_id = promotion_user_option_map.get(selected_promotion_label, "")
            promotion_row = promotion_users_df[promotion_users_df["user_id"] == selected_promotion_user_id].iloc[0]
            target_user = {"role_id": norm_text(promotion_row.get("role_id")), "user_id": selected_promotion_user_id}

            current_role_id = norm_text(promotion_row.get("role_id")).lower()
            current_role_name = role_id_to_name.get(current_role_id, ROLE_LABELS.get(current_role_id, current_role_id))
            st.write(f"{t('current_role')}：{current_role_name}")
            promotion_role_candidates = list(role_name_to_id.keys())
            current_role_name_for_index = role_id_to_name.get(current_role_id, promotion_role_candidates[0])
            role_index = promotion_role_candidates.index(current_role_name_for_index) if current_role_name_for_index in promotion_role_candidates else 0
            new_role_name = st.selectbox(t("new_role"), promotion_role_candidates, index=role_index, key="promotion_new_role")
            new_role_id = role_name_to_id[new_role_name]
            promotion_store_option_map = build_store_option_map(store_id_to_name)
            promotion_store_names = list(promotion_store_option_map.keys())
            current_store_label = get_store_label_by_scope(promotion_store_option_map, norm_text(promotion_row.get("store_scope")))
            if current_store_label not in promotion_store_names:
                current_store_label = promotion_store_names[0]
            store_idx = promotion_store_names.index(current_store_label)
            new_store_name = st.selectbox(t("sync_store"), promotion_store_names, index=store_idx, key="promotion_new_store")
            new_store_scope = promotion_store_option_map[new_store_name]
            promotion_note = st.text_input(t("note"), placeholder=t("note_placeholder"), key="promotion_note")

            promotion_kind = t("role_unchanged")
            if current_role_id in PROMOTION_ROLE_ORDER and new_role_id in PROMOTION_ROLE_ORDER:
                current_idx = PROMOTION_ROLE_ORDER.index(current_role_id)
                new_idx = PROMOTION_ROLE_ORDER.index(new_role_id)
                if new_idx > current_idx:
                    promotion_kind = t("promotion_up")
                elif new_idx < current_idx:
                    promotion_kind = t("promotion_down")
            st.caption(f"{t('current_judgment')}：{promotion_kind}")

            if st.button(t("submit_role_change"), use_container_width=True, key="btn_submit_role_change"):
                if not can_edit_user(current_user, target_user):
                    st.error(t("no_access_user_admin"))
                elif not can_assign_role(current_user, new_role_id):
                    st.error(t("no_access_user_admin"))
                elif requires_specific_store_scope(new_role_id) and new_store_scope == "ALL":
                    st.error(t("role_requires_store"))
                elif is_store_manager_role(new_role_id) and count_active_store_managers(users_df, new_store_scope, exclude_user_id=selected_promotion_user_id) >= 3:
                    st.error(t("store_manager_limit_promotion"))
                else:
                    before = {"role_id": current_role_id, "store_scope": norm_text(promotion_row.get("store_scope")), "is_active": int(promotion_row.get("is_active", 1))}
                    after = {"role_id": new_role_id, "store_scope": new_store_scope, "is_active": int(promotion_row.get("is_active", 1))}
                    try:
                        update_user(
                            selected_promotion_user_id,
                            {
                                "before": before,
                                "after": after,
                                "updates": {
                                    "role_id": new_role_id,
                                    "store_scope": new_store_scope,
                                    "updated_at": now_ts(),
                                    "updated_by": st.session_state.get("login_user", ""),
                                },
                            },
                            action="role_change",
                            note=promotion_note.strip() or f"{promotion_kind}: {current_role_id} -> {new_role_id}",
                        )
                        st.success(t("role_change_done"))
                        st.rerun()
                    except Exception as e:
                        st.error(f"{t('update_failed')}：{e}")

    with tab5:
        st.subheader(t("role_permission_table"))
        st.caption(t("role_permission_caption"))
        permission_df = pd.DataFrame(ROLE_PERMISSION_ROWS)
        st.dataframe(permission_df, use_container_width=True, hide_index=True)
        st.markdown(f"#### {t('supplement')}")
        st.write(t("permission_note_1"))
        st.write(t("permission_note_2"))
        st.write(t("permission_note_3"))
        st.write(t("permission_note_4"))
