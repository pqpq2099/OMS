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


def _safe_active_series(df: pd.DataFrame, col: str = "is_active") -> pd.Series:
    """將啟用欄位統一轉成 1/0，兼容 1 / 1.0 / TRUE / true / yes。"""
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


def _write_back_users_df(users_df: pd.DataFrame):
    """依 users 原始 header，將整張 users 表寫回 Google Sheet。"""
    users_header = get_header("users")
    work = users_df.copy()

    for col in users_header:
        if col not in work.columns:
            work[col] = ""

    work = work[users_header].copy()
    rows = [users_header] + work.fillna("").astype(str).values.tolist()

    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet("users")
    ws.clear()
    ws.update(rows)
    bust_cache()


def _update_user_fields_by_user_id(user_id: str, updates: dict):
    """以 user_id 為唯一鍵，直接更新 users 表指定欄位。"""
    users_df = read_table("users").copy()
    if users_df.empty:
        raise ValueError("users 表沒有資料")

    for col in ["user_id", "updated_at", "updated_by", "password_hash", "must_change_password", "store_scope"]:
        if col not in users_df.columns:
            users_df[col] = ""

    mask = users_df["user_id"].astype(str).str.strip() == str(user_id).strip()
    if not mask.any():
        raise ValueError(f"找不到 user_id：{user_id}")

    for field, value in updates.items():
        if field not in users_df.columns:
            users_df[field] = ""
        users_df.loc[mask, field] = value

    _write_back_users_df(users_df)


def _count_active_store_managers(users_df: pd.DataFrame, store_scope: str, exclude_user_id: str = "") -> int:
    """計算某分店目前啟用中的店長人數。"""
    if users_df.empty:
        return 0

    work = users_df.copy()
    work = _ensure_columns(work, ["user_id", "role_id", "store_scope", "is_active"])
    work["role_id"] = work["role_id"].astype(str).str.strip().str.lower()
    work["store_scope"] = work["store_scope"].astype(str).str.strip()
    work["user_id"] = work["user_id"].astype(str).str.strip()
    work["is_active"] = _safe_active_series(work)

    mask = (work["role_id"] == "store_manager") & (work["store_scope"] == str(store_scope).strip()) & (work["is_active"] == 1)
    if exclude_user_id:
        mask = mask & (work["user_id"] != str(exclude_user_id).strip())
    return int(mask.sum())


# ============================================================
# [U2] 使用者權限主頁
# ============================================================
def page_user_admin():
    st.title("👥 使用者權限")

    login_role_id = str(st.session_state.get("login_role_id", "")).strip().lower()
    if login_role_id not in ["owner", "admin"]:
        st.error("你沒有權限進入此頁。")
        return

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
    users_df["account_code"] = users_df["account_code"].astype(str).str.strip()
    users_df["display_name"] = users_df["display_name"].astype(str).str.strip()
    users_df["role_id"] = users_df["role_id"].astype(str).str.strip()
    users_df["store_scope"] = users_df["store_scope"].astype(str).str.strip()

    users_df["is_active"] = (
        pd.to_numeric(users_df["is_active"], errors="coerce")
        .fillna(1)
        .astype(int)
    )

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

    # 若 roles 表沒有中文名稱，就用程式內建對照補
    if "role_display" in role_map.columns:
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

    store_map_id = stores_df[["store_id", store_label_col]].copy()
    store_map_id = store_map_id.rename(columns={
        "store_id": "store_scope",
        store_label_col: "store_display_by_id",
    })

    store_map_code = stores_df[["store_code", store_label_col]].copy()
    store_map_code = store_map_code.rename(columns={
        "store_code": "store_scope",
        store_label_col: "store_display_by_code",
    })

    # --------------------------------------------------------
    # 顯示用 users_view
    # --------------------------------------------------------
    users_view = active_users_df.merge(
        role_map,
        on="role_id",
        how="left",
    )

    users_view = users_view.merge(
        store_map_id,
        on="store_scope",
        how="left",
    )

    users_view = users_view.merge(
        store_map_code,
        on="store_scope",
        how="left",
    )

    users_view["role_display"] = users_view["role_display"].fillna(
        users_view["role_id"].map(ROLE_LABELS)
    )
    users_view["role_display"] = users_view["role_display"].fillna(users_view["role_id"])

    users_view["store_display"] = users_view["store_display_by_id"].fillna(users_view["store_display_by_code"])
    users_view.loc[users_view["store_scope"] == "ALL", "store_display"] = "全部分店"
    users_view["store_display"] = users_view["store_display"].fillna("未設定")

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

            show_df.columns = [
                "帳號",
                "名稱",
                "角色",
                "分店",
            ]

            
        st.subheader("修改帳號")

        edit_users_df = read_table("users").copy()
        edit_users_df = _ensure_columns(
            edit_users_df,
            ["user_id", "account_code", "display_name", "role_id", "store_scope", "is_active"],
        )

        if edit_users_df.empty:
            st.info("沒有可修改的使用者資料")
        else:
            edit_users_df["account_code"] = edit_users_df["account_code"].astype(str).str.strip()
            edit_users_df["display_name"] = edit_users_df["display_name"].astype(str).str.strip()
            edit_users_df["role_id"] = edit_users_df["role_id"].astype(str).str.strip()
            edit_users_df["store_scope"] = edit_users_df["store_scope"].astype(str).str.strip()
            edit_users_df["is_active"] = _safe_active_series(edit_users_df)

            edit_target_df = edit_users_df[edit_users_df["is_active"] == 1].copy()
            if edit_target_df.empty:
                st.info("目前沒有啟用中的使用者可修改")
            else:
                edit_user_option_map = {
                    f"{str(row.get('display_name', '')).strip() or str(row.get('account_code', '')).strip()}（{str(row.get('account_code', '')).strip()}）": str(row.get("user_id", "")).strip()
                    for _, row in edit_target_df.sort_values(["display_name", "account_code"]).iterrows()
                    if str(row.get("user_id", "")).strip()
                }
                edit_user_options = list(edit_user_option_map.keys())

                if not edit_user_options:
                    st.info("目前沒有可修改的使用者")
                else:
                    selected_edit_user_label = st.selectbox(
                        "選擇要修改帳號的使用者",
                        edit_user_options,
                        key="edit_user_account_select",
                    )
                    selected_edit_user_id = edit_user_option_map.get(selected_edit_user_label, "")

                    edit_target_row = edit_target_df[
                        edit_target_df["user_id"].astype(str).str.strip() == selected_edit_user_id
                    ].copy()

                    if edit_target_row.empty:
                        st.error("找不到選取的使用者資料")
                    else:
                        current_account_code = str(edit_target_row["account_code"].iloc[0]).strip()
                        current_display_name = str(edit_target_row["display_name"].iloc[0]).strip()
                        current_role_id = str(edit_target_row["role_id"].iloc[0]).strip()
                        current_store_scope = str(edit_target_row["store_scope"].iloc[0]).strip()

                        with st.form("form_edit_account_code"):
                            st.caption(
                                f"目前角色：{ROLE_LABELS.get(current_role_id, current_role_id)}｜目前分店：{current_store_scope or 'ALL'}"
                            )
                            edited_account_code = st.text_input(
                                "新帳號",
                                value=current_account_code,
                                placeholder="例如：store_mgr_001",
                            ).strip()
                            edited_display_name = st.text_input(
                                "顯示名稱",
                                value=current_display_name,
                                placeholder="例如：王店長",
                            ).strip()

                            submitted_edit_account = st.form_submit_button(
                                "更新帳號資料",
                                use_container_width=True,
                            )

                        if submitted_edit_account:
                            if not edited_account_code:
                                st.error("帳號不可空白。")
                            elif not edited_display_name:
                                st.error("名稱不可空白。")
                            else:
                                lower_account = edited_account_code.lower()
                                dup_df = edit_users_df.copy()
                                dup_df["account_code_lower"] = dup_df["account_code"].astype(str).str.strip().str.lower()
                                dup_df["user_id"] = dup_df["user_id"].astype(str).str.strip()

                                duplicated = dup_df[
                                    (dup_df["account_code_lower"] == lower_account)
                                    & (dup_df["user_id"] != selected_edit_user_id)
                                ]

                                if not duplicated.empty:
                                    st.error("此帳號已存在，請改用其他帳號。")
                                else:
                                    try:
                                        _update_user_fields_by_user_id(
                                            selected_edit_user_id,
                                            {
                                                "account_code": edited_account_code,
                                                "display_name": edited_display_name,
                                                "updated_at": _now_ts(),
                                                "updated_by": st.session_state.get("login_user", ""),
                                            },
                                        )
                                        st.success("帳號資料已更新。")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"更新失敗：{e}")

        st.divider()

        # ============================================================
        # 重設使用者密碼
        # ============================================================
        st.subheader("重設使用者密碼")

        reset_users_df = read_table("users").copy()

        if reset_users_df.empty:
            st.info("沒有使用者資料")
        else:
            reset_users_df["account_code"] = reset_users_df["account_code"].astype(str)

            account_list = reset_users_df["account_code"].tolist()

            selected_account = st.selectbox(
                "選擇要重設密碼的帳號",
                account_list,
                key="reset_account_select",
            )

            if st.button("重設為預設密碼 123456", use_container_width=True, key="btn_reset_password"):
                default_password = "123456"
                new_hash = _hash_password(default_password)
                now_ts = _now_ts()

                mask = reset_users_df["account_code"] == selected_account

                if mask.sum() == 0:
                    st.error("找不到該使用者")
                else:
                    selected_user_id = str(reset_users_df.loc[mask, "user_id"].iloc[0]).strip()

                    try:
                        _update_user_fields_by_user_id(
                            selected_user_id,
                            {
                                "password_hash": new_hash,
                                "must_change_password": 1,
                                "updated_at": now_ts,
                                "updated_by": st.session_state.get("login_user", ""),
                            },
                        )
                        st.success(f"已重設帳號 {selected_account} 的密碼為 123456。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"重設失敗：{e}")

        st.markdown("---")
        st.subheader("新增使用者")

        # 讀角色與分店資料
        create_roles_df = read_table("roles").copy()
        create_stores_df = read_table("stores").copy()
        create_users_df = read_table("users").copy()

        # 只取啟用中的角色
        if not create_roles_df.empty:
            create_roles_df["is_active"] = _safe_active_series(create_roles_df)
            create_roles_df = create_roles_df[create_roles_df["is_active"] == 1].copy()

        # 只取啟用中的分店
        if not create_stores_df.empty:
            create_stores_df["is_active"] = _safe_active_series(create_stores_df)
            create_stores_df = create_stores_df[create_stores_df["is_active"] == 1].copy()

        # 角色下拉選單：顯示中文，實際寫入 role_id
        role_options = []
        role_label_map = {}

        if not create_roles_df.empty:
            for _, row in create_roles_df.iterrows():
                role_id = str(row.get("role_id", "")).strip()
                role_name_zh = str(row.get("role_name_zh", "")).strip()
                role_name = str(row.get("role_name", "")).strip()

                if not role_id:
                    continue

                label = role_name_zh if role_name_zh else role_name if role_name else role_id
                show_text = f"{label}（{role_id}）"
                role_options.append(show_text)
                role_label_map[show_text] = role_id
        else:
            role_options = [
                "系統負責人（owner）",
                "管理員（admin）",
                "店長（store_manager）",
            ]
            role_label_map = {
                "系統負責人（owner）": "owner",
                "管理員（admin）": "admin",
                "店長（store_manager）": "store_manager",
            }

        # 分店下拉選單
        store_options = ["ALL"]
        store_label_map = {"ALL": "ALL"}

        if not create_stores_df.empty:
            for _, row in create_stores_df.iterrows():
                store_id = str(row.get("store_id", "")).strip()
                store_name_zh = str(row.get("store_name_zh", "")).strip()
                store_name = str(row.get("store_name", "")).strip()

                if not store_id:
                    continue

                label = store_name_zh if store_name_zh else store_name if store_name else store_id
                show_text = f"{label}（{store_id}）"
                store_options.append(show_text)
                store_label_map[show_text] = store_id

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
                work_users = create_users_df.copy()

                if not work_users.empty and "account_code" in work_users.columns:
                    work_users["account_code"] = (
                        work_users["account_code"].astype(str).str.strip().str.lower()
                    )
                    account_exists = new_account_code.strip().lower() in work_users["account_code"].tolist()
                else:
                    account_exists = False

                if account_exists:
                    st.error("此帳號已存在，請改用其他帳號。")
                else:
                    if selected_role_id in ["store_manager", "leader", "test_store_manager", "test_leader"] and selected_store_scope == "ALL":
                        st.error("此角色必須綁定指定分店，不可使用 ALL。")
                    elif selected_role_id == "store_manager" and _count_active_store_managers(create_users_df, selected_store_scope) >= 3:
                        st.error("此分店店長已達 3 位上限，請先調整後再建立。")
                    else:
                        try:
                            new_user_id = allocate_ids({"users": 1})["users"][0]
                        except Exception:
                            new_user_id = f"USER_{datetime.now().strftime('%Y%m%d%H%M%S')}"

                        default_password = "123456"
                        password_hash = _hash_password(default_password)
                        now_ts = _now_ts()

                        new_row = {
                            "user_id": new_user_id,
                            "account_code": new_account_code.strip(),
                            "email": "",
                            "display_name": new_display_name.strip(),
                            "password_hash": password_hash,
                            "must_change_password": 1,
                            "role_id": selected_role_id,
                            "store_scope": selected_store_scope,
                            "is_active": 1,
                            "last_login_at": "",
                            "created_at": now_ts,
                            "created_by": st.session_state.get("login_user", ""),
                            "updated_at": now_ts,
                            "updated_by": st.session_state.get("login_user", ""),
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
            show_manager_df = manager_df[["account_code", "display_name", "store_display"]].copy()
            show_manager_df.columns = ["店長帳號", "店長名稱", "管理分店"]
            st.dataframe(show_manager_df, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.subheader("調整店長分店")

            manager_option_map = {
                f"{row['display_name']}（{row['account_code']}）": row['user_id']
                for _, row in manager_df.sort_values(["display_name", "account_code"]).iterrows()
            }
            manager_options = list(manager_option_map.keys())

            active_stores_df = stores_df.copy()
            active_stores_df["is_active"] = _safe_active_series(active_stores_df)
            active_stores_df = active_stores_df[active_stores_df["is_active"] == 1].copy()

            store_option_map = {}
            store_options = []
            for _, row in active_stores_df.iterrows():
                store_id = str(row.get("store_id", "")).strip()
                store_name = str(row.get("store_name_zh", "")).strip() or str(row.get("store_name", "")).strip() or store_id
                if not store_id:
                    continue
                label = f"{store_name}（{store_id}）"
                store_options.append(label)
                store_option_map[label] = store_id

            if not store_options:
                st.warning("目前沒有可指派的啟用分店。")
            else:
                selected_manager_label = st.selectbox("選擇店長", manager_options, key="mgr_user_select")
                selected_manager_user_id = manager_option_map.get(selected_manager_label, "")

                if not selected_manager_user_id:
                    st.error("找不到選取的店長資料。")
                else:
                    current_scope = str(
                        manager_df.loc[manager_df["user_id"] == selected_manager_user_id, "store_scope"].iloc[0]
                    ).strip()
                    current_store_idx = 0
                    for idx, label in enumerate(store_options):
                        if store_option_map.get(label, "") == current_scope:
                            current_store_idx = idx
                            break

                    selected_store_label = st.selectbox(
                        "改派分店",
                        store_options,
                        index=current_store_idx,
                        key="mgr_store_scope_select",
                    )
                    new_store_scope = store_option_map.get(selected_store_label, "")

                    if st.button("更新店長分店", use_container_width=True, key="btn_update_manager_scope"):
                        if not new_store_scope:
                            st.error("分店資料異常，請重新選擇。")
                        else:
                            current_manager_count = _count_active_store_managers(
                                users_df,
                                new_store_scope,
                                exclude_user_id=selected_manager_user_id,
                            )
                            if current_manager_count >= 3:
                                st.error("此分店店長已達 3 位上限，無法再指派。")
                            else:
                                try:
                                    _update_user_fields_by_user_id(
                                        selected_manager_user_id,
                                        {
                                            "store_scope": new_store_scope,
                                            "updated_at": _now_ts(),
                                            "updated_by": st.session_state.get("login_user", ""),
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
            show_leader_df = leader_df[["account_code", "display_name", "store_display"]].copy()
            show_leader_df.columns = ["組長帳號", "組長名稱", "所屬分店"]
            st.dataframe(show_leader_df, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.subheader("調整組長分店")

            leader_option_map = {
                f"{row['display_name']}（{row['account_code']}）": row['user_id']
                for _, row in leader_df.sort_values(["display_name", "account_code"]).iterrows()
            }
            leader_options = list(leader_option_map.keys())

            active_stores_df = stores_df.copy()
            active_stores_df["is_active"] = _safe_active_series(active_stores_df)
            active_stores_df = active_stores_df[active_stores_df["is_active"] == 1].copy()

            leader_store_option_map = {}
            leader_store_options = []
            for _, row in active_stores_df.iterrows():
                store_id = str(row.get("store_id", "")).strip()
                store_name = str(row.get("store_name_zh", "")).strip() or str(row.get("store_name", "")).strip() or store_id
                if not store_id:
                    continue
                label = f"{store_name}（{store_id}）"
                leader_store_options.append(label)
                leader_store_option_map[label] = store_id

            if not leader_store_options:
                st.warning("目前沒有可指派的啟用分店。")
            else:
                selected_leader_label = st.selectbox("選擇組長", leader_options, key="leader_user_select")
                selected_leader_user_id = leader_option_map.get(selected_leader_label, "")

                if not selected_leader_user_id:
                    st.error("找不到選取的組長資料。")
                else:
                    current_scope = str(
                        leader_df.loc[leader_df["user_id"] == selected_leader_user_id, "store_scope"].iloc[0]
                    ).strip()
                    current_store_idx = 0
                    for idx, label in enumerate(leader_store_options):
                        if leader_store_option_map.get(label, "") == current_scope:
                            current_store_idx = idx
                            break

                    selected_store_label = st.selectbox(
                        "改派分店",
                        leader_store_options,
                        index=current_store_idx,
                        key="leader_store_scope_select",
                    )
                    new_store_scope = leader_store_option_map.get(selected_store_label, "")

                    if st.button("更新組長分店", use_container_width=True, key="btn_update_leader_scope"):
                        if not new_store_scope:
                            st.error("分店資料異常，請重新選擇。")
                        else:
                            try:
                                _update_user_fields_by_user_id(
                                    selected_leader_user_id,
                                    {
                                        "store_scope": new_store_scope,
                                        "updated_at": _now_ts(),
                                        "updated_by": st.session_state.get("login_user", ""),
                                    },
                                )
                                st.success("組長分店已更新。")
                                st.rerun()
                            except Exception as e:
                                st.error(f"更新失敗：{e}")
