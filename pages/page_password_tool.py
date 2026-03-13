"""
頁面模組：密碼工具
用途：產生 Streamlit secrets 的雜湊密碼
"""

import streamlit as st
import streamlit_authenticator as stauth


def page_password_tool():
    st.title("🔐 密碼工具")

    st.write("輸入密碼，系統會產生加密後的 hash。")

    password = st.text_input("輸入密碼", type="password")

    if st.button("產生 hash"):
        if password:
            hashed = stauth.Hasher([password]).generate()[0]
            st.code(hashed)
        else:
            st.warning("請輸入密碼")
