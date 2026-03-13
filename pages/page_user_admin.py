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
1. 沿用目前 OMS 既有架構，不另外建立 utils.gsheets
2. 統一使用 oms_core 的 read_table / append_rows_by_header
3. 此頁只做帳號與角色管理，不負責登入驗證
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pandas as pd
import streamlit as st

from oms_core import (
    read_table,
    append_rows_by_header,
)


# ============================================================
# [U1] 欄位安全輔助
# 用途：
# 1. 避免資料表暫時缺欄位時直接炸掉
# 2. 提供預設值，讓頁面仍可顯示
# ============================================================
def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """確保 DataFrame 至少包含指定欄位，不足時自動補空字串欄位。"""
    work = df.copy()
    for col in columns:
        if col not in work.columns:
            work[col] = ""
    return work


def _pick_first_existing_column(df: pd.DataFrame, candidates: list[str], fallback: str) -> str:
    """從候選欄位中挑第一個存在的欄位，若都不存在則回傳 fallback。"""
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

    # users 若為空，仍建立基本欄位，避免頁面直接壞掉
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

    # 補齊常用欄位
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
        ],
    )

    # --------------------------------------------------------
    # 型別整理
    # --------------------------------------------------------
    users_df["account_code"] = users_df["account_code"].astype(str).str.strip()
    users_df["display_name"] = users_df["display_name"].astype(str).str.strip()
    users_df["role_id"] = users_df["role_id"].astype(str).str.strip()
    users_df["store_scope"] = users_df["store_scope"].astype(str).str.strip()

    # is_active 若為空，預設視為 1，避免舊資料不顯示
    users_df["is_active"] = (
        pd.to_numeric(users_df["is_active"], errors="coerce")
        .fillna(1)
        .astype(int)
    )

    # 只顯示啟用帳號
    active_users_df = users_df[users_df["is_active"] == 1].copy()

    # --------------------------------------------------------
    # 角色顯示名稱處理
    # 優先顯示中文 role_name_zh，沒有再退回 role_name，再沒有就顯示 role_id
    # --------------------------------------------------------
    role_display_col = _pick_first_existing_column(
        roles_df,
        ["role_name_zh", "role_name"],
        "role_id",
    )

    role_map = roles_df[["role_id", role_display_col]].copy()
    role_map = role_map.rename(columns={role_display_col: "role_display"})

    # --------------------------------------------------------
    # 分店顯示名稱處理
    # 優先顯示中文 store_name_zh，沒有再退回 store_name
    # 使用者 store_scope 目前以 store_id 為主
    # 若未來改回 store_code，此段也能相容
    # --------------------------------------------------------
    store_label_col = _pick_first_existing_column(
        stores_df,
        ["store_name_zh", "store_name"],
        "store_id",
    )

    # 同時準備兩種對照：
    # 1. store_scope 對 store_id
    # 2. store_scope 對 store_code
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
    # 建立顯示用 users_view
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

    # 分店名稱優先順序：
    # 1. 以 store_id 對到的名稱
    # 2. 以 store_code 對到的名稱
    # 3. ALL → 全部分店
    # 4. 其他 → 未設定
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

        # ====================================================
        # 新增使用者
        # ====================================================
        st.subheader("新增使用者")

        # 角色選單：直接用 role_id 寫入，避免顯示名稱與實際值錯亂
        role_options = (
            roles_df["role_id"]
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .tolist()
        )

        # 分店選單：以 store_id 為主，若 store_id 全空則退回 store_code
        store_id_options = (
            stores_df["store_id"]
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .tolist()
        )
        store_code_options = (
            stores_df["store_code"]
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .tolist()
        )

        if store_id_options:
            store_options = store_id_options
        else:
            store_options = store_code_options

        with st.form("create_user_form"):
            account_code = st.text_input("帳號", key="user_admin_account_code")
            display_name = st.text_input("名稱", key="user_admin_display_name")

            if role_options:
                role_id = st.selectbox("角色", role_options, key="user_admin_role_id")
            else:
                role_id = st.text_input("角色", value="", key="user_admin_role_id_fallback")

            store_scope = st.selectbox(
                "分店",
                ["ALL"] + store_options,
                key="user_admin_store_scope",
            )

            submit = st.form_submit_button("建立使用者")

        # 表單送出後處理
        if submit:
            account_code = str(account_code).strip()
            display_name = str(display_name).strip()
            role_id = str(role_id).strip()
            store_scope = str(store_scope).strip()

            if not account_code:
                st.error("帳號不可為空")
                return

            if not display_name:
                st.error("名稱不可為空")
                return

            if not role_id:
                st.error("角色不可為空")
                return

            # 帳號重複檢查
            existing_codes = users_df["account_code"].astype(str).str.strip().str.lower().tolist()
            if account_code.lower() in existing_codes:
                st.error("帳號已存在，請換一個帳號")
                return

            # 建立新的 user_id
            new_user_id = "USER_" + uuid.uuid4().hex[:6].upper()

            # 寫入資料列
            new_row = {
                "user_id": new_user_id,
                "account_code": account_code,
                "email": "",
                "display_name": display_name,
                "role_id": role_id,
                "store_scope": store_scope,
                "is_active": 1,
                "last_login_at": "",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "created_by": "system",
                "updated_at": "",
                "updated_by": "",
            }

            append_rows_by_header("users", [new_row])
            st.success("使用者建立成功")
            st.rerun()

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
