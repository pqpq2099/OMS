from __future__ import annotations

import pandas as pd

from users_permissions.logic.user_permission import (
    PROMOTION_ROLE_ORDER,
    ROLE_LABELS,
    can_edit_user,
    is_admin_role,
    can_assign_role,
    count_active_store_managers,
    is_leader_role,
    is_promotion_target_role,
    is_store_manager_role,
    requires_specific_store_scope,
)
from users_permissions.logic.user_query import build_store_option_map, get_store_label_by_scope, norm_text, user_display_label
from users_permissions.logic.user_write import create_user, reset_user_password, toggle_user_active, update_user
from users_permissions.services.service_users import UserServiceError
from ui_text import t


def build_user_list_table(users_view: pd.DataFrame) -> pd.DataFrame:
    if users_view.empty:
        return pd.DataFrame(columns=["帳號", "姓名", "角色", "分店", "狀態", "最後登入"])
    show_df = users_view[["account_code", "display_name", "role_display", "store_display", "status_display", "last_login_at"]].copy()
    show_df.columns = ["帳號", "姓名", "角色", "分店", "狀態", "最後登入"]
    return show_df


def build_user_option_map(users_view: pd.DataFrame, store_id_to_name: dict[str, str]) -> dict[str, str]:
    if users_view.empty:
        return {}
    work = users_view.sort_values(["display_name", "account_code"]).copy()
    return {user_display_label(row, store_id_to_name, ROLE_LABELS): row["user_id"] for _, row in work.iterrows()}


def build_role_filtered_option_map(users_view: pd.DataFrame, store_id_to_name: dict[str, str], role_filter) -> dict[str, str]:
    work = users_view[users_view["role_id"].apply(role_filter)].copy()
    if work.empty:
        return {}
    work = work.sort_values(["display_name", "account_code"])
    return {user_display_label(row, store_id_to_name, ROLE_LABELS): row["user_id"] for _, row in work.iterrows()}


def validate_create_user(ctx, *, account_code: str, display_name: str, role_id: str, store_scope: str):
    work_users = ctx.users_df.copy()
    work_users["account_code"] = work_users["account_code"].astype(str).str.strip().str.lower()
    account_exists = account_code.strip().lower() in work_users["account_code"].tolist()

    if not account_code:
        raise UserServiceError(t("please_enter_account"))
    if not display_name:
        raise UserServiceError(t("please_enter_name"))
    if account_exists:
        raise UserServiceError(t("account_exists"))
    if not can_assign_role(ctx.current_user, role_id):
        raise UserServiceError(t("no_access_user_admin"))
    if requires_specific_store_scope(role_id) and store_scope == "ALL":
        raise UserServiceError(t("role_requires_store"))
    if is_store_manager_role(role_id) and count_active_store_managers(ctx.users_df, store_scope) >= 3:
        raise UserServiceError(t("store_manager_limit_reached_create"))


def submit_create_user(ctx, *, account_code: str, display_name: str, role_id: str, store_scope: str):
    validate_create_user(ctx, account_code=account_code, display_name=display_name, role_id=role_id, store_scope=store_scope)
    return create_user({"account_code": account_code, "display_name": display_name, "role_id": role_id, "store_scope": store_scope})


def validate_edit_user(ctx, *, target_user: dict, role_id: str, store_scope: str, user_id: str):
    if not can_edit_user(ctx.current_user, target_user):
        raise UserServiceError(t("no_access_user_admin"))
    if not can_assign_role(ctx.current_user, role_id):
        raise UserServiceError(t("no_access_user_admin"))
    if requires_specific_store_scope(role_id) and store_scope == "ALL":
        raise UserServiceError(t("role_requires_store"))
    if is_store_manager_role(role_id) and count_active_store_managers(ctx.users_df, store_scope, exclude_user_id=user_id) >= 3:
        raise UserServiceError(t("store_manager_limit_reached_update"))


def submit_update_user(ctx, *, user_id: str, target_user: dict, updates: dict, before: dict, after: dict, action: str = "update_user", note: str = "Admin edited user profile"):
    validate_edit_user(ctx, target_user=target_user, role_id=updates.get("role_id", ""), store_scope=updates.get("store_scope", ""), user_id=user_id)
    return update_user(user_id, {"updates": updates, "before": before, "after": after}, action=action, note=note)


def validate_quick_reset_password(ctx, *, target_user: dict):
    if not can_edit_user(ctx.current_user, target_user):
        raise UserServiceError(t("no_access_user_admin"))


def submit_reset_password(ctx, *, user_id: str, target_user: dict, target_row: dict):
    validate_quick_reset_password(ctx, target_user=target_user)
    return reset_user_password(user_id, target_row)


def validate_toggle_user_active(ctx, *, target_user: dict):
    if not can_edit_user(ctx.current_user, target_user):
        raise UserServiceError(t("no_access_user_admin"))


def submit_toggle_user_active(ctx, *, user_id: str, target_user: dict, target_row: dict, target_next_active: int):
    validate_toggle_user_active(ctx, target_user=target_user)
    return toggle_user_active(user_id, target_row, target_next_active)


def build_store_assignment_names(ctx) -> list[str]:
    return [name for name, sid in ctx.store_name_to_id.items() if sid != "ALL"]


def build_store_permission_panel(ctx, role_filter):
    filtered = ctx.users_view[ctx.users_view["role_id"].apply(role_filter)].copy()
    option_map = build_role_filtered_option_map(ctx.users_view, ctx.store_id_to_name, role_filter)
    return filtered, option_map, build_store_assignment_names(ctx)


def validate_store_reassign(ctx, *, target_user: dict, target_role_id: str, new_store_scope: str, user_id: str):
    if not can_edit_user(ctx.current_user, target_user):
        raise UserServiceError(t("no_access_user_admin"))
    if is_store_manager_role(target_role_id) and count_active_store_managers(ctx.users_df, new_store_scope, exclude_user_id=user_id) >= 3:
        raise UserServiceError(t("store_manager_limit_assign"))


def submit_store_reassign(ctx, *, user_id: str, target_user: dict, target_role_id: str, current_store_scope: str, new_store_scope: str, action: str, note: str):
    validate_store_reassign(ctx, target_user=target_user, target_role_id=target_role_id, new_store_scope=new_store_scope, user_id=user_id)
    before = {"store_scope": current_store_scope}
    after = {"store_scope": new_store_scope}
    return update_user(user_id, {"updates": {"store_scope": new_store_scope}, "before": before, "after": after}, action=action, note=note)


def build_promotion_state(ctx):
    promotion_users_df = ctx.users_view[ctx.users_view["role_id"].apply(is_promotion_target_role)].copy()
    option_map = build_role_filtered_option_map(ctx.users_view, ctx.store_id_to_name, is_promotion_target_role)
    return promotion_users_df, option_map


def get_promotion_kind(current_role_id: str, new_role_id: str, labels: dict[str, str]) -> str:
    promotion_kind = labels.get("unchanged", "角色不變")
    if current_role_id in PROMOTION_ROLE_ORDER and new_role_id in PROMOTION_ROLE_ORDER:
        current_idx = PROMOTION_ROLE_ORDER.index(current_role_id)
        new_idx = PROMOTION_ROLE_ORDER.index(new_role_id)
        if new_idx > current_idx:
            promotion_kind = labels.get("up", "升階")
        elif new_idx < current_idx:
            promotion_kind = labels.get("down", "降階")
    return promotion_kind


def validate_promotion_change(ctx, *, target_user: dict, new_role_id: str, new_store_scope: str, user_id: str):
    if not can_edit_user(ctx.current_user, target_user):
        raise UserServiceError(t("no_access_user_admin"))
    if not can_assign_role(ctx.current_user, new_role_id):
        raise UserServiceError(t("no_access_user_admin"))
    if requires_specific_store_scope(new_role_id) and new_store_scope == "ALL":
        raise UserServiceError(t("role_requires_store"))
    if is_store_manager_role(new_role_id) and count_active_store_managers(ctx.users_df, new_store_scope, exclude_user_id=user_id) >= 3:
        raise UserServiceError(t("store_manager_limit_promotion"))


def submit_promotion_change(ctx, *, user_id: str, target_user: dict, current_role_id: str, current_store_scope: str, new_role_id: str, new_store_scope: str, note: str, promotion_kind: str):
    validate_promotion_change(ctx, target_user=target_user, new_role_id=new_role_id, new_store_scope=new_store_scope, user_id=user_id)
    before = {"role_id": current_role_id, "store_scope": current_store_scope, "is_active": 1}
    after = {"role_id": new_role_id, "store_scope": new_store_scope, "is_active": 1}
    final_note = note.strip() or f"{promotion_kind}: {current_role_id} -> {new_role_id}"
    return update_user(
        user_id,
        {"updates": {"role_id": new_role_id, "store_scope": new_store_scope}, "before": before, "after": after},
        action="role_change",
        note=final_note,
    )


def get_store_label_for_scope(option_map: dict[str, str], scope: str) -> str:
    return get_store_label_by_scope(option_map, scope)


def build_store_option_map_public(store_id_to_name: dict[str, str]) -> dict[str, str]:
    return build_store_option_map(store_id_to_name)


def build_account_edit_create_state(ctx):
    role_options = list(ctx.role_name_to_id.keys())
    store_option_map = build_store_option_map(ctx.store_id_to_name)
    return {
        "role_options": role_options,
        "store_option_map": store_option_map,
        "store_options": list(store_option_map.keys()),
    }


def build_account_edit_user_options(ctx):
    editable_users_df = ctx.users_view.sort_values(["display_name", "account_code"]).copy()
    edit_user_option_map = build_user_option_map(editable_users_df, ctx.store_id_to_name)
    return {
        "editable_users_df": editable_users_df,
        "edit_user_option_map": edit_user_option_map,
        "edit_user_labels": list(edit_user_option_map.keys()),
    }


def build_account_edit_selected_state(ctx, selected_edit_user_id: str):
    editable_users_df = ctx.users_view.sort_values(["display_name", "account_code"]).copy()
    if editable_users_df.empty:
        return {
            "edit_row": pd.Series(dtype=object),
            "target_user": {"role_id": "", "user_id": ""},
            "edit_role_names": list(ctx.role_name_to_id.keys()),
            "edit_role_index": 0,
            "edit_store_option_map": build_store_option_map(ctx.store_id_to_name),
            "edit_store_names": list(build_store_option_map(ctx.store_id_to_name).keys()),
            "edit_store_index": 0,
        }
    target_rows = editable_users_df[editable_users_df["user_id"] == selected_edit_user_id]
    edit_row = target_rows.iloc[0] if not target_rows.empty else editable_users_df.iloc[0]
    selected_user_id = norm_text(edit_row.get("user_id"))
    target_user = {"role_id": norm_text(edit_row.get("role_id")), "user_id": selected_user_id}
    edit_role_names = list(ctx.role_name_to_id.keys())
    current_role_name = ctx.role_id_to_name.get(norm_text(edit_row.get("role_id")), norm_text(edit_row.get("role_id")))
    edit_role_index = edit_role_names.index(current_role_name) if current_role_name in edit_role_names else 0
    edit_store_option_map = build_store_option_map(ctx.store_id_to_name)
    edit_store_names = list(edit_store_option_map.keys())
    current_store_label = get_store_label_by_scope(edit_store_option_map, norm_text(edit_row.get("store_scope")))
    if edit_store_names and current_store_label not in edit_store_names:
        current_store_label = edit_store_names[0]
    edit_store_index = edit_store_names.index(current_store_label) if edit_store_names else 0
    return {
        "edit_row": edit_row,
        "target_user": target_user,
        "edit_role_names": edit_role_names,
        "edit_role_index": edit_role_index,
        "edit_store_option_map": edit_store_option_map,
        "edit_store_names": edit_store_names,
        "edit_store_index": edit_store_index,
    }


def build_promotion_selected_state(ctx, selected_promotion_user_id: str):
    promotion_users_df, _ = build_promotion_state(ctx)
    if promotion_users_df.empty:
        return {}
    target_rows = promotion_users_df[promotion_users_df["user_id"] == selected_promotion_user_id]
    promotion_row = target_rows.iloc[0] if not target_rows.empty else promotion_users_df.iloc[0]
    selected_user_id = norm_text(promotion_row.get("user_id"))
    current_role_id = norm_text(promotion_row.get("role_id")).lower()
    promotion_role_candidates = list(ctx.role_name_to_id.keys())
    current_role_name = ctx.role_id_to_name.get(current_role_id, ROLE_LABELS.get(current_role_id, current_role_id))
    current_role_name_for_index = ctx.role_id_to_name.get(current_role_id, promotion_role_candidates[0] if promotion_role_candidates else "")
    role_index = promotion_role_candidates.index(current_role_name_for_index) if current_role_name_for_index in promotion_role_candidates else 0
    promotion_store_option_map = build_store_option_map(ctx.store_id_to_name)
    promotion_store_names = list(promotion_store_option_map.keys())
    current_store_label = get_store_label_by_scope(promotion_store_option_map, norm_text(promotion_row.get("store_scope")))
    if promotion_store_names and current_store_label not in promotion_store_names:
        current_store_label = promotion_store_names[0]
    store_idx = promotion_store_names.index(current_store_label) if promotion_store_names else 0
    return {
        "promotion_row": promotion_row,
        "selected_promotion_user_id": selected_user_id,
        "target_user": {"role_id": current_role_id, "user_id": selected_user_id},
        "current_role_id": current_role_id,
        "current_role_name": current_role_name,
        "promotion_role_candidates": promotion_role_candidates,
        "role_index": role_index,
        "promotion_store_option_map": promotion_store_option_map,
        "promotion_store_names": promotion_store_names,
        "store_idx": store_idx,
    }


def build_store_permission_display_df(filtered_df: pd.DataFrame) -> pd.DataFrame:
    if filtered_df.empty:
        return pd.DataFrame()
    return filtered_df[["account_code", "display_name", "store_display", "status_display"]].copy()


def build_store_permission_selected_state(ctx, filtered_df: pd.DataFrame, selected_user_id: str):
    if filtered_df.empty:
        return {}
    target_rows = filtered_df[filtered_df["user_id"] == selected_user_id]
    row = target_rows.iloc[0] if not target_rows.empty else filtered_df.iloc[0]
    selected_user_id = norm_text(row.get("user_id"))
    store_names_only = build_store_assignment_names(ctx)
    current_store_name = ctx.store_id_to_name.get(norm_text(row.get("store_scope")), store_names_only[0] if store_names_only else "")
    if store_names_only and current_store_name not in store_names_only:
        current_store_name = store_names_only[0]
    store_idx = store_names_only.index(current_store_name) if store_names_only else 0
    return {
        "row": row,
        "selected_user_id": selected_user_id,
        "target_user": {"role_id": norm_text(row.get("role_id")), "user_id": selected_user_id},
        "store_names_only": store_names_only,
        "store_idx": store_idx,
    }


def build_user_quick_manage_state(ctx, selected_user_id: str):
    managed_target_df = ctx.users_view.sort_values(["display_name", "account_code"]).copy()
    if managed_target_df.empty:
        return {"managed_target_df": managed_target_df, "user_option_map": {}}
    user_option_map = build_user_option_map(managed_target_df, ctx.store_id_to_name)
    target_rows = managed_target_df[managed_target_df["user_id"] == selected_user_id]
    target_row = target_rows.iloc[0] if not target_rows.empty else managed_target_df.iloc[0]
    resolved_user_id = norm_text(target_row.get("user_id"))
    target_next_active = 0 if int(target_row.get("is_active", 1)) == 1 else 1
    return {
        "managed_target_df": managed_target_df,
        "user_option_map": user_option_map,
        "target_row": target_row,
        "target_user": {"role_id": norm_text(target_row.get("role_id")), "user_id": resolved_user_id},
        "selected_user_id": resolved_user_id,
        "target_next_active": target_next_active,
    }



def resolve_create_user_store_label(store_options: list[str], current_label: str, selected_role_id: str, all_stores_label: str):
    resolved_label = current_label
    if not resolved_label or resolved_label not in store_options:
        if all_stores_label in store_options:
            resolved_label = next((x for x in store_options if x != all_stores_label), all_stores_label)
        else:
            resolved_label = store_options[0] if store_options else ""
    if is_admin_role(selected_role_id):
        if all_stores_label in store_options:
            resolved_label = all_stores_label
    elif resolved_label == all_stores_label:
        non_all_options = [x for x in store_options if x != all_stores_label]
        resolved_label = non_all_options[0] if non_all_options else (store_options[0] if store_options else "")
    return resolved_label


def build_account_edit_submit_payload(ctx, edit_row, edit_display_name: str, edit_role_name: str, edit_store_name: str, edit_is_active_label: str, active_label: str):
    new_role_id = ctx.role_name_to_id[edit_role_name]
    edit_store_option_map = build_store_option_map(ctx.store_id_to_name)
    new_store_scope = edit_store_option_map[edit_store_name]
    new_is_active = 1 if edit_is_active_label == active_label else 0
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
    return {
        "updates": after.copy(),
        "before": before,
        "after": after,
        "new_role_id": new_role_id,
        "new_store_scope": new_store_scope,
        "new_is_active": new_is_active,
    }


def build_promotion_form_state(ctx, selected_state: dict, new_role_name: str, new_store_name: str, labels: dict[str, str]):
    current_role_id = selected_state["current_role_id"]
    new_role_id = ctx.role_name_to_id[new_role_name]
    promotion_store_option_map = selected_state["promotion_store_option_map"]
    new_store_scope = promotion_store_option_map[new_store_name]
    promotion_kind = get_promotion_kind(current_role_id, new_role_id, labels)
    return {
        "new_role_id": new_role_id,
        "new_store_scope": new_store_scope,
        "promotion_kind": promotion_kind,
    }


def build_store_reassign_form_state(ctx, selected_state: dict, new_store_name: str, *, action: str, note: str):
    row = selected_state["row"]
    return {
        "user_id": selected_state["selected_user_id"],
        "target_user": selected_state["target_user"],
        "target_role_id": norm_text(row.get("role_id")),
        "current_store_scope": norm_text(row.get("store_scope")),
        "new_store_scope": ctx.store_name_to_id[new_store_name],
        "action": action,
        "note": note,
    }


def build_user_quick_manage_display(selected_state: dict, labels: dict[str, str]):
    target_row = selected_state["target_row"]
    target_next_active = selected_state["target_next_active"]
    return {
        "target_label": labels["disable"] if target_next_active == 0 else labels["enable"],
        "role_text": norm_text(target_row.get("role_display")),
        "store_text": norm_text(target_row.get("store_display")),
        "status_text": norm_text(target_row.get("status_display")),
    }
