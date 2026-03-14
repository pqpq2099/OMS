"""
頁面模組：使用者與權限管理

功能：
1. 顯示使用者列表
2. 新增使用者
3. 店長管理
4. 組長管理

資料來源：
Google Sheet
- users
- roles
- stores

設計原則：
1. 沿用目前 OMS 既有架構
2. 統一使用 oms_core 的 read_table / append_rows_by_header / get_header / allocate_ids
3. 此頁只做帳號與角色管理，不負責登入驗證
"""

from __future__ import annotations

from datetime import datetime
import hashlib

import pandas as pd
import streamlit as st

from oms_core import (
    read_table,
    append_rows_by_header,
    get_header,
    allocate_ids,
    get_spreadsheet,
    bust_cache,
)


def _hash_password(password: str) -> str:
    """把明碼轉成 SHA256，和目前登入頁一致。"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _now_ts() -> str:
    """回傳目前時間字串。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 角色中文顯示
ROLE_LABELS = {
    "owner": "系統負責人",
    "admin": "管理員",
    "store_manager": "店長",
    "leader": "組長",
    "test_admin": "測試管理員",
    "test_store_manager": "測試店長",
    "test_leader": "測試組長",
}


# ============================================================
# [U1] 欄位安全輔助
# ============================================================
def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """確保 DataFrame 至少包含指定欄位，不足時自動補空字串欄位。"""
    work = df.copy()
    for col in columns:
        if col not in work.columns:
            work[col] = ""
    return work


def _pick_first_existing_column(df: pd.DataFrame, candidates: list[str], fallback: str) -> str:
    """從候選欄位中挑第一個存在的欄位。"""
    for col in candidates:
        if col in df.columns:
            return col
    return fallback


def _find_user_row_index(user_id: str) -> int | None:
    """在 users 分頁中依 user_id 找出實際列號。"""
    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet("users")
    values = ws.get_all_values()
    if not values:
        return None

    headers = [str(c).strip() for c in values[0]]
    if "user_id" not in headers:
        return None

    user_col_idx = headers.index("user_id")
    for row_idx, row in enumerate(values[1:], start=2):
        cell_value = row[user_col_idx] if user_col_idx < len(row) else ""
        if str(cell_value).strip() == str(user_id).strip():
            return row_idx

    return None


def _update_user_fields(user_id: str, updates: dict):
    """直接將指定欄位寫回 users 表。"""
    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet("users")
    values = ws.get_all_values()
    if not values:
        raise ValueError("users 分頁為空，無法更新資料。")

    headers = [str(c).strip() for c in values[0]]
    row_idx = _find_user_row_index(user_id)
    if row_idx is None:
        raise ValueError(f"找不到 user_id：{user_id}")

    for field, value in updates.items():
        if field not in headers:
            continue
        col_idx = headers.index(field) + 1
        ws.update_cell(row_idx, col_idx, value)

    bust_cache()


def _count_active_store_managers(users_df: pd.DataFrame, store_scope: str, exclude_user_id: str = "") -> int:
    """計算某分店目前啟用中的正式店長數量。"""
    if users_df.empty:
        return 0

    work = _ensure_columns(users_df, ["user_id", "role_id", "store_scope", "is_active"]).copy()
    work["role_id"] = work["role_id"].astype(str).str.strip().str.lower()
    work["store_scope"] = work["store_scope"].astype(str).str.strip()
    work["user_id"] = work["user_id"].astype(str).str.strip()
    work["is_active"] = pd.to_numeric(work["is_active"], errors="coerce").fillna(1).astype(int)

    if exclude_user_id:
        work = work[work["user_id"] != str(exclude_user_id).strip()].copy()

    mask = (
        (work["is_active"] == 1)
        & (work["role_id"] == "store_manager")
        & (work["store_scope"] == str(store_scope).strip())
    )
    return int(mask.sum())


def _build_store_option_maps(stores_df: pd.DataFrame) -> tuple[list[str], dict[str, str], dict[str, str]]:
    """建立分店下拉選單與顯示對照。"""
    work = _ensure_columns(
        stores_df,
        ["store_id", "store_code", "store_name", "store_name_zh", "is_active"],
    ).copy()

    if "is_active" in work.columns:
        work["is_active"] = pd.to_numeric(work["is_active"], errors="coerce").fillna(1).astype(int)
        work = work[work["is_active"] == 1].copy()

    options = ["ALL"]
    label_to_scope = {"ALL": "ALL"}
    scope_to_label = {"ALL": "全部分店"}

    for _, row in work.iterrows():
        store_id = str(row.get("store_id", "")).strip()
        if not store_id:
            continue
        store_name_zh = str(row.get("store_name_zh", "")).strip()
        store_name = str(row.get("store_name", "")).strip()
        label = store_name_zh or store_name or store_id
        show_text = f"{label}（{store_id}）"
        options.append(show_text)
        label_to_scope[show_text] = store_id
        scope_to_label[store_id] = label

        store_code = str(row.get("store_code", "")).strip()
        if store_code and store_code not in scope_to_label:
            scope_to_label[store_code] = label

    return options, label_to_scope, scope_to_label


# ============================================================
# [U2] 使用者權限主頁
# ============================================================
def page_user_admin():
    st.title("👥 使用者權限")

    # --------------------------------------------------------
    # 頁面權限：只有 owner / admin 可進入
    # --------------------------------------------------------
    login_role = str(st.session_state.get("login_role_id", "")).strip().lower()
    if login_role not in ["owner", "admin"]:
        st.error("你沒有權限進入此頁。")
        return

    actor_user = str(st.session_state.get("login_user", "")).strip()

    # --------------------------------------------------------
    # 讀取資料表
    # --------------------------------------------------------
    users_df = read_table("users")
    roles_df = read_table("roles")
    stores_df = read_table("stores")

    # users 若為空，先建立基本欄位，避免頁面壞掉
    if users_df.empty:
        users_df = pd.DataFrame(columns=[
            "user_id",
            "account_code",
            "email",
            "display_name",
            "password_hash",
            "must_change_password",
            "role_id",
            "store_scope",
            "is_active",
            "last_login_at",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
        ])

    users_df = _ensure_columns(
        users_df,
        [
            "user_id",
            "account_code",
            "email",
            "display_name",
            "password_hash",
            "must_change_password",
            "role_id",
            "store_scope",
            "is_active",
            "last_login_at",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
        ],
    )

    roles_df = _ensure_columns(
        roles_df,
        [
            "role_id",
            "role_name",
            "role_name_zh",
            "is_active",
        ],
    )

    stores_df = _ensure_columns(
        stores_df,
        [
            "store_id",
            "store_code",
            "store_name",
            "store_name_zh",
            "is_active",
        ],
    )

    # --------------------------------------------------------
    # 型別整理
    # --------------------------------------------------------
    users_df["user_id"] = users_df["user_id"].astype(str).str.strip()
    users_df["account_code"] = users_df["account_code"].astype(str).str.strip()
    users_df["display_name"] = users_df["display_name"].astype(str).str.strip()
    users_df["role_id"] = users_df["role_id"].astype(str).str.strip().str.lower()
    users_df["store_scope"] = users_df["store_scope"].astype(str).str.strip()
    users_df["is_active"] = pd.to_numeric(users_df["is_active"], errors="coerce").fillna(1).astype(int)

    roles_df["role_id"] = roles_df["role_id"].astype(str).str.strip().str.lower()
    if "is_active" in roles_df.columns:
        roles_df["is_active"] = pd.to_numeric(roles_df["is_active"], errors="coerce").fillna(1).astype(int)
        roles_df = roles_df[roles_df["is_active"] == 1].copy()

    stores_df["store_id"] = stores_df["store_id"].astype(str).str.strip()
    stores_df["store_code"] = stores_df["store_code"].astype(str).str.strip()
    if "is_active" in stores_df.columns:
        stores_df["is_active"] = pd.to_numeric(stores_df["is_active"], errors="coerce").fillna(1).astype(int)

    active_users_df = users_df[users_df["is_active"] == 1].copy()

    # --------------------------------------------------------
    # 角色顯示名稱處理
    # --------------------------------------------------------
    role_display_col = _pick_first_existing_column(
        roles_df,
        ["role_name_zh", "role_name"],
        "role_id",
    )

    role_map = roles_df[["role_id", role_display_col]].copy()
    role_map = role_map.rename(columns={role_display_col: "role_display"})
    role_map["role_display"] = role_map["role_display"].replace("", pd.NA)
    role_map["role_display"] = role_map["role_display"].fillna(
        role_map["role_id"].map(ROLE_LABELS)
    )
    role_map["role_display"] = role_map["role_display"].fillna(role_map["role_id"])

    # --------------------------------------------------------
    # 分店顯示名稱處理
    # --------------------------------------------------------
    store_label_col = _pick_first_existing_column(
        stores_df,
        ["store_name_zh", "store_name"],
        "store_id",
    )

    store_map_id = stores_df[["store_id", store_label_col]].copy().rename(columns={
        "store_id": "store_scope",
        store_label_col: "store_display_by_id",
    })
    store_map_code = stores_df[["store_code", store_label_col]].copy().rename(columns={
        "store_code": "store_scope",
        store_label_col: "store_display_by_code",
    })

    # --------------------------------------------------------
    # 顯示用 users_view
    # --------------------------------------------------------
    users_view = active_users_df.merge(role_map, on="role_id", how="left")
    users_view = users_view.merge(store_map_id, on="store_scope", how="left")
    users_view = users_view.merge(store_map_code, on="store_scope", how="left")

    users_view["role_display"] = users_view["role_display"].fillna(
        users_view["role_id"].map(ROLE_LABELS)
    )
    users_view["role_display"] = users_view["role_display"].fillna(users_view["role_id"])
    users_view["store_display"] = users_view["store_display_by_id"].fillna(users_view["store_display_by_code"])
    users_view.loc[users_view["store_scope"] == "ALL", "store_display"] = "全部分店"
    users_view["store_display"] = users_view["store_display"].fillna("未設定")

    store_options, store_label_map, scope_to_label = _build_store_option_maps(stores_df)

    # --------------------------------------------------------
    # 建立三個分頁
    # --------------------------------------------------------
    tab1, tab2, tab3 = st.tabs([
        "使用者列表",
        "店長管理",
        "組長管理",
    ])

    # ========================================================
    # TAB 1 使用者列表
    # ========================================================
    with tab1:
        st.subheader("使用者列表")

        if users_view.empty:
            st.info("目前尚無使用者資料")
        else:
            show_df = users_view[
                ["account_code", "display_name", "role_display", "store_display"]
            ].copy()
            show_df.columns = ["帳號", "名稱", "角色", "分店"]
            st.dataframe(show_df, use_container_width=True, hide_index=True)

        st.divider()

        # ============================================================
        # 重設使用者密碼
        # ============================================================
        st.subheader("重設使用者密碼")

        reset_users_df = active_users_df.copy()
        if reset_users_df.empty:
            st.info("沒有使用者資料")
        else:
            reset_users_df = reset_users_df.sort_values(["account_code", "display_name"])
            reset_users_df["reset_label"] = reset_users_df.apply(
                lambda r: f"{str(r.get('account_code', '')).strip()}｜{str(r.get('display_name', '')).strip()}",
                axis=1,
            )
            reset_options = reset_users_df["reset_label"].tolist()
            selected_reset_label = st.selectbox(
                "選擇要重設密碼的帳號",
                reset_options,
                key="reset_account_select",
            )

            if st.button("重設為預設密碼 123456", use_container_width=True, key="btn_reset_password"):
                target_row = reset_users_df[reset_users_df["reset_label"] == selected_reset_label]
                if target_row.empty:
                    st.error("找不到該使用者")
                else:
                    user_id = str(target_row.iloc[0].get("user_id", "")).strip()
                    try:
                        _update_user_fields(
                            user_id,
                            {
                                "password_hash": _hash_password("123456"),
                                "must_change_password": 1,
                                "updated_at": _now_ts(),
                                "updated_by": actor_user,
                            },
                        )
                        st.success("密碼已重設為 123456，使用者下次登入需先修改密碼。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"重設失敗：{e}")

        st.markdown("---")
        st.subheader("新增使用者")

        # 角色下拉選單：顯示中文，實際寫入 role_id
        role_options = []
        role_label_map = {}
        if not roles_df.empty:
            for _, row in roles_df.iterrows():
                role_id = str(row.get("role_id", "")).strip().lower()
                role_name_zh = str(row.get("role_name_zh", "")).strip()
                role_name = str(row.get("role_name", "")).strip()
                if not role_id:
                    continue
                label = role_name_zh or role_name or role_id
                show_text = f"{label}（{role_id}）"
                role_options.append(show_text)
                role_label_map[show_text] = role_id
        else:
            role_options = [
                "系統負責人（owner）",
                "管理員（admin）",
                "店長（store_manager）",
                "組長（leader）",
            ]
            role_label_map = {
                "系統負責人（owner）": "owner",
                "管理員（admin）": "admin",
                "店長（store_manager）": "store_manager",
                "組長（leader）": "leader",
            }

        with st.form("form_create_user", clear_on_submit=True):
            new_account_code = st.text_input("帳號", placeholder="例如：jenny").strip()
            new_display_name = st.text_input("名稱", placeholder="例如：Jenny").strip()
            selected_role_label = st.selectbox("角色", options=role_options, index=0)
            selected_role_id = role_label_map[selected_role_label]

            if selected_role_id in ["owner", "admin", "test_admin"]:
                default_store_index = 0
            else:
                default_store_index = 1 if len(store_options) > 1 else 0

            selected_store_label = st.selectbox("分店", options=store_options, index=default_store_index)
            selected_store_scope = store_label_map[selected_store_label]

            st.caption("預設密碼：123456")
            st.caption("建立後，使用者第一次登入會被要求修改密碼。")
            submitted = st.form_submit_button("建立使用者", use_container_width=True)

        if submitted:
            if not new_account_code:
                st.error("請輸入帳號。")
            elif not new_display_name:
                st.error("請輸入名稱。")
            else:
                account_exists = new_account_code.strip().lower() in (
                    users_df["account_code"].astype(str).str.strip().str.lower().tolist()
                )
                if account_exists:
                    st.error("此帳號已存在，請改用其他帳號。")
                elif selected_role_id in ["store_manager", "leader", "test_store_manager", "test_leader"] and selected_store_scope == "ALL":
                    st.error("此角色必須綁定指定分店，不可使用 ALL。")
                elif selected_role_id == "store_manager" and _count_active_store_managers(users_df, selected_store_scope) >= 3:
                    st.error("此分店已達 3 位店長上限，請先調整原有店長設定。")
                else:
                    try:
                        new_user_id = allocate_ids({"users": 1})["users"][0]
                    except Exception:
                        new_user_id = f"USER_{datetime.now().strftime('%Y%m%d%H%M%S')}"

                    now_ts = _now_ts()
                    new_row = {
                        "user_id": new_user_id,
                        "account_code": new_account_code.strip(),
                        "email": "",
                        "display_name": new_display_name.strip(),
                        "password_hash": _hash_password("123456"),
                        "must_change_password": 1,
                        "role_id": selected_role_id,
                        "store_scope": selected_store_scope,
                        "is_active": 1,
                        "last_login_at": "",
                        "created_at": now_ts,
                        "created_by": actor_user,
                        "updated_at": now_ts,
                        "updated_by": actor_user,
                    }

                    try:
                        users_header = get_header("users")
                        append_rows_by_header("users", users_header, [new_row])
                        st.success(
                            f"建立成功。帳號：{new_account_code.strip()}｜預設密碼：123456｜第一次登入需修改密碼。"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"建立失敗：{e}")

    # ========================================================
    # TAB 2 店長管理
    # ========================================================
    with tab2:
        st.subheader("店長管理")
        manager_df = users_view[users_view["role_id"] == "store_manager"].copy()

        if manager_df.empty:
            st.info("目前沒有店長資料")
        else:
            show_manager_df = manager_df[
                ["account_code", "display_name", "store_display"]
            ].copy()
            show_manager_df.columns = ["店長帳號", "店長名稱", "管理分店"]
            st.dataframe(show_manager_df, use_container_width=True, hide_index=True)

            st.caption("店長可重新指派分店；每間分店最多 3 位正式店長。")
            manager_options = manager_df.apply(
                lambda r: f"{str(r.get('account_code', '')).strip()}｜{str(r.get('display_name', '')).strip()}",
                axis=1,
            ).tolist()
            selected_manager_label = st.selectbox(
                "選擇要調整的店長",
                manager_options,
                key="manager_select_user",
            )
            selected_manager_row = manager_df[
                manager_df.apply(
                    lambda r: f"{str(r.get('account_code', '')).strip()}｜{str(r.get('display_name', '')).strip()}",
                    axis=1,
                ) == selected_manager_label
            ].iloc[0]
            current_scope = str(selected_manager_row.get("store_scope", "")).strip()
            current_store_label = scope_to_label.get(current_scope, current_scope or "未設定")
            manager_store_options = [opt for opt in store_options if opt != "ALL"]
            if not manager_store_options:
                st.warning("目前沒有可用分店，無法調整店長。")
            else:
                default_manager_index = 0
                for idx, opt in enumerate(manager_store_options):
                    if store_label_map.get(opt) == current_scope:
                        default_manager_index = idx
                        break
                new_manager_store_label = st.selectbox(
                    "改派管理分店",
                    manager_store_options,
                    index=default_manager_index,
                    key="manager_select_store",
                )
                st.caption(f"目前分店：{current_store_label}")
                if st.button("更新店長分店", use_container_width=True, key="btn_update_manager_scope"):
                    new_scope = store_label_map[new_manager_store_label]
                    user_id = str(selected_manager_row.get("user_id", "")).strip()
                    if not user_id:
                        st.error("找不到該店長的 user_id。")
                    elif new_scope == current_scope:
                        st.info("分店未變更，不需更新。")
                    elif _count_active_store_managers(users_df, new_scope, exclude_user_id=user_id) >= 3:
                        st.error("目標分店已達 3 位店長上限，無法再新增。")
                    else:
                        try:
                            _update_user_fields(
                                user_id,
                                {
                                    "store_scope": new_scope,
                                    "updated_at": _now_ts(),
                                    "updated_by": actor_user,
                                },
                            )
                            st.success("店長分店已更新。")
                            st.rerun()
                        except Exception as e:
                            st.error(f"更新失敗：{e}")

    # ========================================================
    # TAB 3 組長管理
    # ========================================================
    with tab3:
        st.subheader("組長管理")
        leader_df = users_view[users_view["role_id"] == "leader"].copy()

        if leader_df.empty:
            st.info("目前沒有組長資料")
        else:
            show_leader_df = leader_df[
                ["account_code", "display_name", "store_display"]
            ].copy()
            show_leader_df.columns = ["組長帳號", "組長名稱", "所屬分店"]
            st.dataframe(show_leader_df, use_container_width=True, hide_index=True)

            leader_options = leader_df.apply(
                lambda r: f"{str(r.get('account_code', '')).strip()}｜{str(r.get('display_name', '')).strip()}",
                axis=1,
            ).tolist()
            selected_leader_label = st.selectbox(
                "選擇要調整的組長",
                leader_options,
                key="leader_select_user",
            )
            selected_leader_row = leader_df[
                leader_df.apply(
                    lambda r: f"{str(r.get('account_code', '')).strip()}｜{str(r.get('display_name', '')).strip()}",
                    axis=1,
                ) == selected_leader_label
            ].iloc[0]
            current_scope = str(selected_leader_row.get("store_scope", "")).strip()
            current_store_label = scope_to_label.get(current_scope, current_scope or "未設定")
            leader_store_options = [opt for opt in store_options if opt != "ALL"]
            if not leader_store_options:
                st.warning("目前沒有可用分店，無法調整組長。")
            else:
                default_leader_index = 0
                for idx, opt in enumerate(leader_store_options):
                    if store_label_map.get(opt) == current_scope:
                        default_leader_index = idx
                        break
                new_leader_store_label = st.selectbox(
                    "改派所屬分店",
                    leader_store_options,
                    index=default_leader_index,
                    key="leader_select_store",
                )
                st.caption(f"目前分店：{current_store_label}")
                if st.button("更新組長分店", use_container_width=True, key="btn_update_leader_scope"):
                    new_scope = store_label_map[new_leader_store_label]
                    user_id = str(selected_leader_row.get("user_id", "")).strip()
                    if not user_id:
                        st.error("找不到該組長的 user_id。")
                    elif new_scope == current_scope:
                        st.info("分店未變更，不需更新。")
                    else:
                        try:
                            _update_user_fields(
                                user_id,
                                {
                                    "store_scope": new_scope,
                                    "updated_at": _now_ts(),
                                    "updated_by": actor_user,
                                },
                            )
                            st.success("組長分店已更新。")
                            st.rerun()
                        except Exception as e:
                            st.error(f"更新失敗：{e}")
