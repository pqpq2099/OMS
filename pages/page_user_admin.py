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
此頁只做帳號與角色管理，不負責登入驗證。
"""

import streamlit as st
import pandas as pd
from datetime import datetime

# OMS 核心函式
from oms_core import (
    read_table,
    append_rows_by_header,
    allocate_ids,
)


# ============================================================
# [U1] 使用者權限主頁
# ============================================================
def page_user_admin():

    st.title("👥 使用者權限")

    # --------------------------------------------------------
    # 讀取資料表
    # --------------------------------------------------------
    users_df = read_table("users")
    roles_df = read_table("roles")
    stores_df = read_table("stores")

    if users_df.empty:
        st.warning("users 資料表沒有資料")
        return

    # 只顯示啟用帳號
    users_df = users_df[users_df["is_active"] == 1]

    # --------------------------------------------------------
    # 建立三個分頁
    # --------------------------------------------------------
    tab1, tab2, tab3 = st.tabs([
        "使用者列表",
        "店長管理",
        "組長管理"
    ])

    # ========================================================
    # TAB 1 使用者列表
    # ========================================================
    with tab1:

        st.subheader("使用者列表")

        # 顯示主要欄位
        show_df = users_df[
            ["account_code", "display_name", "role_id", "store_scope"]
        ].copy()

        show_df.columns = [
            "帳號",
            "名稱",
            "角色",
            "分店"
        ]

        st.dataframe(show_df, use_container_width=True)

        st.divider()

        # ====================================================
        # 新增使用者
        # ====================================================
        st.subheader("新增使用者")

        with st.form("create_user_form"):

            account_code = st.text_input("帳號")
            display_name = st.text_input("名稱")

            # 角色選單
            role_options = roles_df["role_id"].tolist()
            role_id = st.selectbox("角色", role_options)

            # 分店選單
            store_options = stores_df["store_code"].tolist()
            store_scope = st.selectbox("分店", ["ALL"] + store_options)

            submit = st.form_submit_button("建立使用者")

            if submit:

                if not account_code:
                    st.error("帳號不可為空")
                    return

                # ------------------------------------------------
                # 產生新的 user_id
                # ------------------------------------------------
                new_user_id = allocate_ids({"users": 1})["users"][0]

                # ------------------------------------------------
                # 建立新資料列
                # ------------------------------------------------
                from datetime import datetime
                import uuid
                
                new_row = {
                    "user_id": f"USER_{uuid.uuid4().hex[:8]}",
                    "account_code": "",
                    "email": "",
                    "display_name": new_name,
                    "role_id": new_role,
                    "store_scope": new_store,
                    "is_active": 1,
                    "last_login_at": "",
                    "created_at": datetime.now().isoformat(),
                    "created_by": "owner",
                    "updated_at": "",
                    "updated_by": "",
                }

                # ------------------------------------------------
                # 寫入 users 表
                # ------------------------------------------------
                append_rows_by_header("users", [new_row])

                st.success("使用者建立成功")
                st.rerun()

    # ========================================================
    # TAB 2 店長管理
    # ========================================================
    with tab2:

        st.subheader("店長管理")

        manager_df = users_df[
            users_df["role_id"] == "store_manager"
        ]

        show_df = manager_df[
            ["account_code", "display_name", "store_scope"]
        ].copy()

        show_df.columns = [
            "店長帳號",
            "店長名稱",
            "管理分店"
        ]

        st.dataframe(show_df, use_container_width=True)

    # ========================================================
    # TAB 3 組長管理
    # ========================================================
    with tab3:

        st.subheader("組長管理")

        leader_df = users_df[
            users_df["role_id"] == "leader"
        ]

        show_df = leader_df[
            ["account_code", "display_name", "store_scope"]
        ].copy()

        show_df.columns = [
            "組長帳號",
            "組長名稱",
            "所屬分店"
        ]

        st.dataframe(show_df, use_container_width=True)
