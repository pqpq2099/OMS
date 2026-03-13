"""
頁面模組：使用者與權限管理

功能：
1. 顯示使用者列表
2. 新增使用者
3. 店長管理
4. 組長管理

資料來源：
Google Sheet → users / roles / stores

權限邏輯：
role_id
owner / admin / store_manager / leader

store_scope
ALL / S001 / S002 / S003
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from oms_core import (
    read_table,
    append_rows_by_header,
    allocate_ids,
)


# ============================================================
# [U1] 使用者管理頁主入口
# ============================================================
def page_user_admin():

    st.title("👥 使用者權限")

    tab1, tab2, tab3 = st.tabs([
        "使用者列表",
        "店長管理",
        "組長管理"
    ])

    # ========================================================
    # 讀取資料表
    # ========================================================
    users_df = read_table("users")
    roles_df = read_table("roles")
    stores_df = read_table("stores")

    if users_df.empty:
        st.warning("users 表沒有資料")
        return

    # 只顯示啟用帳號
    users_df = users_df[users_df["is_active"] == 1]


    # ========================================================
    # TAB 1：使用者列表
    # ========================================================
    with tab1:

        st.subheader("使用者列表")

        view = users_df[
            ["account_code", "display_name", "role_id", "store_scope"]
        ].copy()

        view.columns = [
            "帳號",
            "名稱",
            "角色",
            "分店"
        ]

        st.dataframe(view, use_container_width=True)

        st.divider()

        # ----------------------------------------------------
        # 新增使用者
        # ----------------------------------------------------
        st.subheader("新增使用者")

        with st.form("create_user"):

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

                # 產生 user_id
                new_id = allocate_ids("users", 1)[0]

                new_row = {
                    "user_id": new_id,
                    "account_code": account_code,
                    "email": "",
                    "display_name": display_name,
                    "role_id": role_id,
                    "store_scope": store_scope,
                    "is_active": 1,
                    "last_login_at": "",
                    "created_at": datetime.now(),
                    "created_by": "system",
                    "updated_at": "",
                    "updated_by": "",
                }

                append_rows_by_header("users", [new_row])

                st.success("使用者建立成功")
                st.rerun()


    # ========================================================
    # TAB 2：店長管理
    # ========================================================
    with tab2:

        st.subheader("店長管理")

        manager_df = users_df[
            users_df["role_id"] == "store_manager"
        ]

        view = manager_df[
            ["account_code", "display_name", "store_scope"]
        ].copy()

        view.columns = [
            "店長帳號",
            "店長名稱",
            "管理分店"
        ]

        st.dataframe(view, use_container_width=True)


    # ========================================================
    # TAB 3：組長管理
    # ========================================================
    with tab3:

        st.subheader("組長管理")

        leader_df = users_df[
            users_df["role_id"] == "leader"
        ]

        view = leader_df[
            ["account_code", "display_name", "store_scope"]
        ].copy()

        view.columns = [
            "組長帳號",
            "組長名稱",
            "所屬分店"
        ]

        st.dataframe(view, use_container_width=True)
