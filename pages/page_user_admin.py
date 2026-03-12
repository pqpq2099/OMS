"""
頁面模組：使用者與權限管理。
這一頁正式接上：
1. 使用者列表
2. 店長指派
3. 組長指派

目前走簡化可用版：
- 直接維護 users 資料表
- 依 role_id 與 store_scope 做管理
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from oms_core import _get_active_df, _norm, _now_ts, allocate_ids, overwrite_table, read_table


# ============================================================
# [U0] 共用輔助
# ============================================================
def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    work = df.copy() if df is not None else pd.DataFrame()
    for col in columns:
        if col not in work.columns:
            work[col] = ""
    return work


def _role_label_map(roles_df: pd.DataFrame) -> dict[str, str]:
    if roles_df.empty:
        return {}
    mapping = {}
    for _, row in roles_df.iterrows():
        role_id = _norm(row.get("role_id", ""))
        if not role_id:
            continue
        mapping[role_id] = _norm(row.get("role_name_zh", "")) or _norm(row.get("role_name", "")) or role_id
    return mapping


def _store_label_map(stores_df: pd.DataFrame) -> dict[str, str]:
    if stores_df.empty:
        return {}
    mapping = {}
    for _, row in stores_df.iterrows():
        store_id = _norm(row.get("store_id", ""))
        if not store_id:
            continue
        mapping[store_id] = _norm(row.get("store_name_zh", "")) or _norm(row.get("store_name", "")) or store_id
    return mapping


def _split_store_scope(text: str) -> list[str]:
    return [x.strip() for x in str(text).replace("；", ",").replace("、", ",").split(",") if x.strip()]


# ============================================================
# [U1] 使用者列表
# ============================================================
def _render_users_tab(users_df: pd.DataFrame, roles_df: pd.DataFrame, stores_df: pd.DataFrame):
    st.subheader("使用者列表")

    role_map = _role_label_map(roles_df)
    store_map = _store_label_map(stores_df)

    if not users_df.empty:
        view_df = users_df.copy()
        if "role_id" in view_df.columns:
            view_df["角色"] = view_df["role_id"].astype(str).map(lambda x: role_map.get(str(x).strip(), str(x).strip()))
        if "store_scope" in view_df.columns:
            view_df["分店範圍"] = view_df["store_scope"].astype(str).map(
                lambda x: ", ".join([store_map.get(s, s) for s in _split_store_scope(x)])
            )
        show_cols = [c for c in ["user_id", "account_code", "display_name", "email", "角色", "分店範圍", "is_active"] if c in view_df.columns]
        st.dataframe(view_df[show_cols], use_container_width=True, hide_index=True)
    else:
        st.info("目前沒有 users 資料。")

    st.markdown("---")
    st.markdown("#### 新增使用者")

    role_ids = list(role_map.keys()) or ["owner", "admin", "store_manager", "leader"]
    store_ids = list(store_map.keys())

    with st.form("form_add_user"):
        c1, c2 = st.columns(2)
        account_code = c1.text_input("帳號代碼", value="")
        display_name = c2.text_input("顯示名稱", value="")
        email = c1.text_input("Email", value="")
        role_id = c2.selectbox("角色", options=role_ids, format_func=lambda x: role_map.get(x, x))
        store_scope = st.multiselect("可管理分店", options=store_ids, format_func=lambda x: store_map.get(x, x))
        is_active = st.toggle("啟用", value=True)
        submit = st.form_submit_button("新增使用者", use_container_width=True)

    if submit:
        if not account_code.strip() or not display_name.strip():
            st.warning("帳號代碼與顯示名稱不可空白。")
            return
        try:
            new_id = allocate_ids({"users": 1}).get("users", [""])
            user_id = new_id[0] if new_id else f"USER_{len(users_df)+1:06d}"
            row = {c: "" for c in users_df.columns}
            row.update({
                "user_id": user_id,
                "account_code": account_code.strip(),
                "display_name": display_name.strip(),
                "email": email.strip(),
                "role_id": role_id,
                "store_scope": ",".join(store_scope),
                "is_active": "true" if is_active else "false",
                "created_at": _now_ts(),
                "updated_at": _now_ts(),
            })
            users_df = pd.concat([users_df, pd.DataFrame([row])], ignore_index=True)
            overwrite_table("users", users_df)
            st.success(f"已新增使用者：{user_id}")
            st.rerun()
        except Exception as e:
            st.error(f"新增使用者失敗：{e}")


# ============================================================
# [U2] 店長管理
# ============================================================
def _render_store_manager_tab(users_df: pd.DataFrame, roles_df: pd.DataFrame, stores_df: pd.DataFrame):
    st.subheader("店長管理")

    role_map = _role_label_map(roles_df)
    store_map = _store_label_map(stores_df)

    if users_df.empty:
        st.info("目前沒有 users 資料。")
        return

    manager_ids = []
    for _, row in users_df.iterrows():
        role_id = _norm(row.get("role_id", ""))
        role_name = role_map.get(role_id, role_id).lower()
        if role_id == "store_manager" or "店長" in role_map.get(role_id, "") or role_name == "store_manager":
            manager_ids.append(_norm(row.get("user_id", "")))

    user_label_map = {
        _norm(r.get("user_id", "")): f"{_norm(r.get('display_name', '')) or _norm(r.get('account_code', ''))}｜{_norm(r.get('user_id',''))}"
        for _, r in users_df.iterrows() if _norm(r.get("user_id", ""))
    }

    target_user_id = st.selectbox("選擇店長", options=manager_ids if manager_ids else list(user_label_map.keys()), format_func=lambda x: user_label_map.get(x, x), key="target_store_manager")
    if not target_user_id:
        return

    idx_list = users_df[users_df["user_id"].astype(str).str.strip() == target_user_id].index
    if len(idx_list) == 0:
        return
    idx = idx_list[0]
    current_scope = _split_store_scope(users_df.loc[idx, "store_scope"] if "store_scope" in users_df.columns else "")
    store_ids = list(store_map.keys())

    with st.form("form_store_manager_scope"):
        selected_scope = st.multiselect("指派分店", options=store_ids, default=[x for x in current_scope if x in store_ids], format_func=lambda x: store_map.get(x, x))
        submit = st.form_submit_button("儲存店長分店範圍", use_container_width=True)

    if submit:
        users_df.loc[idx, "store_scope"] = ",".join(selected_scope)
        users_df.loc[idx, "updated_at"] = _now_ts()
        overwrite_table("users", users_df)
        st.success("店長分店範圍已更新。")
        st.rerun()


# ============================================================
# [U3] 組長管理
# ============================================================
def _render_leader_tab(users_df: pd.DataFrame, roles_df: pd.DataFrame, stores_df: pd.DataFrame):
    st.subheader("組長管理")

    role_map = _role_label_map(roles_df)
    store_map = _store_label_map(stores_df)

    if users_df.empty:
        st.info("目前沒有 users 資料。")
        return

    leader_ids = []
    for _, row in users_df.iterrows():
        role_id = _norm(row.get("role_id", ""))
        role_name_zh = role_map.get(role_id, "")
        if role_id == "leader" or "組長" in role_name_zh.lower() or role_name_zh == "組長":
            leader_ids.append(_norm(row.get("user_id", "")))

    user_label_map = {
        _norm(r.get("user_id", "")): f"{_norm(r.get('display_name', '')) or _norm(r.get('account_code', ''))}｜{_norm(r.get('user_id',''))}"
        for _, r in users_df.iterrows() if _norm(r.get("user_id", ""))
    }

    target_user_id = st.selectbox("選擇組長", options=leader_ids if leader_ids else list(user_label_map.keys()), format_func=lambda x: user_label_map.get(x, x), key="target_leader")
    if not target_user_id:
        return

    idx_list = users_df[users_df["user_id"].astype(str).str.strip() == target_user_id].index
    if len(idx_list) == 0:
        return
    idx = idx_list[0]
    current_scope = _split_store_scope(users_df.loc[idx, "store_scope"] if "store_scope" in users_df.columns else "")
    store_ids = list(store_map.keys())

    with st.form("form_leader_scope"):
        selected_scope = st.multiselect("指派分店", options=store_ids, default=[x for x in current_scope if x in store_ids], format_func=lambda x: store_map.get(x, x))
        submit = st.form_submit_button("儲存組長分店範圍", use_container_width=True)

    if submit:
        users_df.loc[idx, "store_scope"] = ",".join(selected_scope)
        users_df.loc[idx, "updated_at"] = _now_ts()
        overwrite_table("users", users_df)
        st.success("組長分店範圍已更新。")
        st.rerun()


# ============================================================
# [U4] 使用者管理頁主入口
# ============================================================
def page_user_admin():
    st.title("👥 使用者權限")
    st.caption("此頁已接上 users / roles / stores，可同時支援本機 Excel / Google 試算表。")

    users_df = _ensure_columns(read_table("users"), [
        "user_id", "account_code", "email", "display_name", "role_id", "store_scope",
        "is_active", "last_login_at", "created_at", "created_by", "updated_at", "updated_by"
    ])
    roles_df = read_table("roles")
    stores_df = read_table("stores")

    tab1, tab2, tab3 = st.tabs(["使用者列表", "店長管理", "組長管理"])

    with tab1:
        _render_users_tab(users_df, roles_df, stores_df)
    with tab2:
        _render_store_manager_tab(users_df, roles_df, stores_df)
    with tab3:
        _render_leader_tab(users_df, roles_df, stores_df)
