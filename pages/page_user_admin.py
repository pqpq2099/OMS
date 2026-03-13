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


# ============================================================
# [U2] 使用者權限主頁
# ============================================================
def page_user_admin():
    st.title("👥 使用者權限")

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

            st.dataframe(show_df, use_container_width=True, hide_index=True)

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
                    reset_users_df.loc[mask, "password_hash"] = new_hash
                    reset_users_df.loc[mask, "must_change_password"] = 1
                    reset_users_df.loc[mask, "updated_at"] = now_ts
                    reset_users_df.loc[mask, "updated_by"] = st.session_state.get("login_user", "")

                    st.warning("目前這段只是記憶體內修改，若要真正寫回 users 表，需改成更新指定列的寫法。")

        st.markdown("---")
        st.subheader("新增使用者")

        # 讀角色與分店資料
        create_roles_df = read_table("roles").copy()
        create_stores_df = read_table("stores").copy()
        create_users_df = read_table("users").copy()

        # 只取啟用中的角色
        if not create_roles_df.empty and "is_active" in create_roles_df.columns:
            create_roles_df["is_active"] = pd.to_numeric(
                create_roles_df["is_active"], errors="coerce"
            ).fillna(0)
            create_roles_df = create_roles_df[create_roles_df["is_active"] == 1].copy()

        # 只取啟用中的分店
        if not create_stores_df.empty and "is_active" in create_stores_df.columns:
            create_stores_df["is_active"] = pd.to_numeric(
                create_stores_df["is_active"], errors="coerce"
            ).fillna(0)
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
                    else:
                        try:
                            new_user_id = allocate_ids("users", 1)[0]
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
                            append_rows_by_header("users", [new_row])
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

            show_manager_df.columns = [
                "店長帳號",
                "店長名稱",
                "管理分店",
            ]

            st.dataframe(show_manager_df, use_container_width=True, hide_index=True)

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

            show_leader_df.columns = [
                "組長帳號",
                "組長名稱",
                "所屬分店",
            ]

            st.dataframe(show_leader_df, use_container_width=True, hide_index=True)
            st.dataframe(show_leader_df, use_container_width=True, hide_index=True)
