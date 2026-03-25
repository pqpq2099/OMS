from __future__ import annotations

import streamlit as st

from users_permissions.logic.logic_user_admin import (
    build_promotion_form_state,
    build_promotion_selected_state,
    build_promotion_state,
    submit_promotion_change,
)
from users_permissions.services.service_users import UserServiceError
from ui_text import t


def render_tab_promotion(ctx):
    st.subheader(t("promotion_title"))
    st.caption(t("promotion_caption"))
    promotion_users_df, promotion_user_option_map = build_promotion_state(ctx)
    if promotion_users_df.empty:
        st.info(t("no_promotion_target"))
        return

    promotion_labels = list(promotion_user_option_map.keys())
    selected_promotion_label = st.selectbox(t("select_employee"), promotion_labels, key="promotion_target_user")
    selected_promotion_user_id = promotion_user_option_map.get(selected_promotion_label, "")
    selected_state = build_promotion_selected_state(ctx, selected_promotion_user_id)
    promotion_row = selected_state["promotion_row"]
    target_user = selected_state["target_user"]

    current_role_id = selected_state["current_role_id"]
    st.write(f"{t('current_role')}：{selected_state['current_role_name']}")
    promotion_role_candidates = selected_state["promotion_role_candidates"]
    new_role_name = st.selectbox(t("new_role"), promotion_role_candidates, index=selected_state["role_index"], key="promotion_new_role")
    promotion_store_names = selected_state["promotion_store_names"]
    new_store_name = st.selectbox(t("sync_store"), promotion_store_names, index=selected_state["store_idx"], key="promotion_new_store")
    promotion_note = st.text_input(t("note"), placeholder=t("note_placeholder"), key="promotion_note")

    promotion_form_state = build_promotion_form_state(
        ctx,
        selected_state,
        new_role_name,
        new_store_name,
        {"unchanged": t("role_unchanged"), "up": t("promotion_up"), "down": t("promotion_down")},
    )
    new_role_id = promotion_form_state["new_role_id"]
    new_store_scope = promotion_form_state["new_store_scope"]
    promotion_kind = promotion_form_state["promotion_kind"]
    st.caption(f"{t('current_judgment')}：{promotion_kind}")

    if st.button(t("submit_role_change"), use_container_width=True, key="btn_submit_role_change"):
        try:
            submit_promotion_change(
                ctx,
                user_id=selected_promotion_user_id,
                target_user=target_user,
                current_role_id=current_role_id,
                current_store_scope=selected_state["current_store_scope"],
                new_role_id=new_role_id,
                new_store_scope=new_store_scope,
                note=promotion_note,
                promotion_kind=promotion_kind,
            )
            st.success(t("role_change_done"))
            st.rerun()
        except UserServiceError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"{t('update_failed')}：{e}")
