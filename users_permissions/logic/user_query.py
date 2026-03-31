from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from shared.services.data_backend import get_table_versions, read_table




@dataclass
class UserAdminContext:
    current_user: dict
    users_df: pd.DataFrame
    roles_df: pd.DataFrame
    stores_df: pd.DataFrame
    managed_users_df: pd.DataFrame
    users_view: pd.DataFrame
    store_id_to_name: dict
    store_name_to_id: dict
    role_id_to_name: dict
    role_name_to_id: dict


_USER_ADMIN_TABLES = ("users", "roles", "stores")


def load_user_admin_tables() -> dict[str, pd.DataFrame]:
    versions = get_table_versions(_USER_ADMIN_TABLES)
    cache = st.session_state.get("_user_admin_tables_cache")
    if isinstance(cache, dict) and cache.get("versions") == versions:
        data = cache.get("data", {})
        if data:
            return {k: v.copy() for k, v in data.items()}

    data = {name: read_table(name) for name in _USER_ADMIN_TABLES}
    st.session_state["_user_admin_tables_cache"] = {
        "versions": versions,
        "data": {k: v.copy() for k, v in data.items()},
    }
    return {k: v.copy() for k, v in data.items()}


def clear_user_admin_tables_cache():
    st.session_state.pop("_user_admin_tables_cache", None)


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    work = df.copy()
    for col in columns:
        if col not in work.columns:
            work[col] = ""
    return work


def pick_first_existing_column(df: pd.DataFrame, candidates: list[str], fallback: str) -> str:
    for col in candidates:
        if col in df.columns:
            return col
    return fallback


def norm_text(value) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def safe_active_series(df: pd.DataFrame, col: str = "is_active") -> pd.Series:
    if col not in df.columns:
        return pd.Series([1] * len(df), index=df.index)

    raw = df[col].copy()
    raw_str = raw.astype(str).str.strip().str.lower()
    true_mask = raw_str.isin(["1", "1.0", "true", "yes", "y"])
    false_mask = raw_str.isin(["0", "0.0", "false", "no", "n"])

    result = pd.Series(1, index=df.index, dtype="int64")
    result.loc[false_mask] = 0
    result.loc[true_mask] = 1

    numeric_mask = ~(true_mask | false_mask)
    if numeric_mask.any():
        numeric_values = pd.to_numeric(raw[numeric_mask], errors="coerce")
        result.loc[numeric_mask] = numeric_values.fillna(1).astype(int)

    return result


def load_users_df() -> pd.DataFrame:
    users_df = load_user_admin_tables()["users"].copy()
    if users_df.empty:
        users_df = pd.DataFrame(columns=[
            "user_id", "account_code", "email", "display_name", "password_hash",
            "must_change_password", "role_id", "store_scope", "is_active",
            "last_login_at", "created_at", "created_by", "updated_at", "updated_by",
        ])

    users_df = ensure_columns(
        users_df,
        [
            "user_id", "account_code", "email", "display_name", "password_hash",
            "must_change_password", "role_id", "store_scope", "is_active",
            "last_login_at", "created_at", "created_by", "updated_at", "updated_by",
        ],
    )
    users_df["account_code"] = users_df["account_code"].astype(str).str.strip()
    users_df["display_name"] = users_df["display_name"].astype(str).str.strip()
    users_df["role_id"] = users_df["role_id"].astype(str).str.strip().str.lower()
    users_df["store_scope"] = users_df["store_scope"].astype(str).str.strip()
    users_df["is_active"] = safe_active_series(users_df)
    return users_df


def load_roles_df() -> pd.DataFrame:
    return ensure_columns(
        load_user_admin_tables()["roles"],
        ["role_id", "role_name", "role_name_zh", "is_active"],
    )


def load_stores_df() -> pd.DataFrame:
    return ensure_columns(
        load_user_admin_tables()["stores"],
        ["store_id", "store_code", "store_name", "store_name_zh", "is_active"],
    )


def build_store_maps(stores_df: pd.DataFrame) -> tuple[dict[str, str], dict[str, str]]:
    active_stores_df = stores_df.copy()
    active_stores_df["is_active"] = safe_active_series(active_stores_df)
    active_stores_df = active_stores_df[active_stores_df["is_active"] == 1].copy()

    store_id_to_name = {"ALL": "全部分店"}
    store_name_to_id = {"全部分店": "ALL"}
    for _, row in active_stores_df.iterrows():
        store_id = norm_text(row.get("store_id"))
        store_name = norm_text(row.get("store_name_zh")) or norm_text(row.get("store_name")) or store_id
        if not store_id:
            continue
        store_id_to_name[store_id] = store_name
        store_name_to_id[store_name] = store_id
    return store_id_to_name, store_name_to_id


def build_store_option_map(store_id_to_name: dict[str, str]) -> dict[str, str]:
    option_map: dict[str, str] = {}
    if "ALL" in store_id_to_name:
        option_map["全部分店"] = "ALL"

    normal_store_ids = [sid for sid in store_id_to_name.keys() if sid != "ALL"]
    for sid in normal_store_ids:
        sname = norm_text(store_id_to_name.get(sid)) or sid
        label = sname
        if label in option_map:
            dup_no = 2
            while f"{label} ({dup_no})" in option_map:
                dup_no += 1
            label = f"{label} ({dup_no})"
        option_map[label] = sid
    return option_map


def get_store_label_by_scope(store_option_map: dict[str, str], store_scope: str) -> str:
    target_scope = norm_text(store_scope)
    for label, sid in store_option_map.items():
        if norm_text(sid) == target_scope:
            return label
    return next(iter(store_option_map.keys()), "")


def build_role_maps(roles_df: pd.DataFrame, role_labels: dict[str, str], login_role_id: str) -> tuple[dict[str, str], dict[str, str]]:
    active_roles_df = roles_df.copy()
    active_roles_df["is_active"] = safe_active_series(active_roles_df)
    active_roles_df = active_roles_df[active_roles_df["is_active"] == 1].copy()

    role_id_to_name: dict[str, str] = {}
    role_name_to_id: dict[str, str] = {}
    for _, row in active_roles_df.iterrows():
        role_id = norm_text(row.get("role_id")).lower()
        role_name = norm_text(row.get("role_name_zh")) or norm_text(row.get("role_name")) or role_labels.get(role_id, role_id)
        if not role_id or role_id == "owner":
            continue
        role_id_to_name[role_id] = role_name
        role_name_to_id[role_name] = role_id

    if not role_id_to_name:
        base_roles = {
            "admin": "管理員",
            "store_manager": "店長",
            "leader": "組長",
            "staff": "一般員工",
            "test_admin": "測試管理員",
            "test_store_manager": "測試店長",
            "test_leader": "測試組長",
        }
        role_id_to_name.update(base_roles)
        role_name_to_id.update({v: k for k, v in base_roles.items()})

    if login_role_id != "owner":
        for blocked_role in ["admin", "test_admin"]:
            role_name = role_id_to_name.pop(blocked_role, None)
            if role_name:
                role_name_to_id.pop(role_name, None)
    return role_id_to_name, role_name_to_id


def user_display_label(row: pd.Series, store_id_to_name: dict[str, str], role_labels: dict[str, str]) -> str:
    name = norm_text(row.get("display_name")) or norm_text(row.get("account_code"))
    account = norm_text(row.get("account_code"))
    role_id = norm_text(row.get("role_id")).lower()
    role_name = role_labels.get(role_id, role_id)
    store_scope = norm_text(row.get("store_scope"))
    store_name = store_id_to_name.get(store_scope, store_scope or "未設定")
    return f"{name}（{account} / {role_name} / {store_name}）"


def build_users_view(users_df: pd.DataFrame, roles_df: pd.DataFrame, stores_df: pd.DataFrame, role_labels: dict[str, str]) -> pd.DataFrame:
    role_display_col = pick_first_existing_column(roles_df, ["role_name_zh", "role_name"], "role_id")
    role_map = roles_df[["role_id", role_display_col]].copy().rename(columns={role_display_col: "role_display"})
    role_map["role_id"] = role_map["role_id"].astype(str).str.strip().str.lower()

    store_label_col = pick_first_existing_column(stores_df, ["store_name_zh", "store_name"], "store_id")
    store_map = stores_df[["store_id", store_label_col]].copy().rename(columns={"store_id": "store_scope", store_label_col: "store_display"})
    store_map["store_scope"] = store_map["store_scope"].astype(str).str.strip()

    users_view = users_df.copy()
    users_view["store_scope"] = users_view["store_scope"].astype(str).str.strip()
    users_view = users_view.merge(role_map, on="role_id", how="left")
    users_view = users_view.merge(store_map, on="store_scope", how="left")
    users_view["role_display"] = users_view["role_display"].fillna(users_view["role_id"].map(role_labels))
    users_view["role_display"] = users_view["role_display"].fillna(users_view["role_id"])
    users_view.loc[users_view["store_scope"] == "ALL", "store_display"] = "全部分店"
    users_view["store_display"] = users_view["store_display"].fillna("未設定")
    users_view["status_display"] = users_view["is_active"].map({1: "啟用", 0: "停用"}).fillna("停用")
    return users_view


def build_user_admin_context(current_user_role_id: str, current_user_id: str, role_labels: dict[str, str]) -> UserAdminContext:
    current_user = {
        "role_id": norm_text(current_user_role_id).lower(),
        "user_id": norm_text(current_user_id),
    }

    users_df = load_users_df()
    roles_df = load_roles_df()
    stores_df = load_stores_df()

    managed_users_df = users_df[users_df["role_id"] != "owner"].copy().reset_index(drop=True)
    users_view = build_users_view(managed_users_df, roles_df, stores_df, role_labels)
    store_id_to_name, store_name_to_id = build_store_maps(stores_df)
    role_id_to_name, role_name_to_id = build_role_maps(roles_df, role_labels, current_user["role_id"])

    return UserAdminContext(
        current_user=current_user,
        users_df=users_df,
        roles_df=roles_df,
        stores_df=stores_df,
        managed_users_df=managed_users_df,
        users_view=users_view,
        store_id_to_name=store_id_to_name,
        store_name_to_id=store_name_to_id,
        role_id_to_name=role_id_to_name,
        role_name_to_id=role_name_to_id,
    )
