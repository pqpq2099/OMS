import streamlit as st
import pandas as pd
import hashlib

from oms_core import read_table


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def page_login():

    st.title("系統登入")

    account = st.text_input("帳號")
    password = st.text_input("密碼", type="password")

    if st.button("登入"):

        users = read_table("users")

        user = users[users["account_code"] == account]

        if user.empty:
            st.error("帳號不存在")
            return

        user = user.iloc[0]

        if user["password_hash"] != hash_password(password):
            st.error("密碼錯誤")
            return

        st.session_state["login_user"] = user["user_id"]
        st.session_state["role_id"] = user["role_id"]

        st.success("登入成功")
        st.rerun()
