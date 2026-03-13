import streamlit as st
import pandas as pd
import uuid
from datetime import datetime

from utils.gsheets import load_table, append_rows_by_header


def page_user_admin():

    st.title("使用者管理")

    # ----------------------------------
    # 讀取資料
    # ----------------------------------

    users_df = load_table("users")
    roles_df = load_table("roles")
    stores_df = load_table("stores")

    # ----------------------------------
    # 使用者列表
    # ----------------------------------

    st.subheader("使用者列表")

    role_map = roles_df[["role_id", "role_name"]].copy()

    users_view = users_df.merge(
        role_map,
        on="role_id",
        how="left"
    )

    show_df = users_view[
        ["account_code", "display_name", "role_name", "store_scope"]
    ].copy()

    show_df.columns = [
        "帳號",
        "名稱",
        "角色",
        "分店"
    ]

    st.dataframe(show_df, use_container_width=True)

    st.divider()

    # ----------------------------------
    # 新增使用者
    # ----------------------------------

    st.subheader("新增使用者")

    with st.form("create_user_form"):

        account_code = st.text_input(
            "帳號",
            key="new_user_account"
        )

        display_name = st.text_input(
            "名稱",
            key="new_user_name"
        )

        role_options = roles_df["role_id"].tolist()

        role_id = st.selectbox(
            "角色",
            role_options,
            key="new_user_role"
        )

        store_options = stores_df["store_code"].tolist()

        store_scope = st.selectbox(
            "分店",
            ["ALL"] + store_options,
            key="new_user_store"
        )

        submit = st.form_submit_button("建立使用者")

    # ----------------------------------
    # 建立使用者
    # ----------------------------------

    if submit:

        if not account_code:
            st.error("帳號不可為空")
            return

        if not display_name:
            st.error("名稱不可為空")
            return

        # 產生 user_id
        new_user_id = "USER_" + uuid.uuid4().hex[:6].upper()

        new_row = {
            "user_id": new_user_id,
            "account_code": account_code,
            "email": "",
            "display_name": display_name,
            "role_id": role_id,
            "store_scope": store_scope,
            "is_active": 1,
            "last_login_at": "",
            "created_at": datetime.now().isoformat(),
            "created_by": "system",
            "updated_at": "",
            "updated_by": ""
        }

        append_rows_by_header("users", [new_row])

        st.success("使用者建立成功")

        st.rerun()
