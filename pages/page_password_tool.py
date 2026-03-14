"""
頁面模組：密碼工具

用途：
1. 輸入明碼
2. 產生 SHA256 password_hash
3. 複製後可貼回 users.password_hash

設計原則：
- 與目前登入系統完全一致
- 不依賴額外套件
"""

import hashlib
import streamlit as st


def _hash_password(password: str) -> str:
    """將明碼轉成 SHA256，與目前登入頁一致。"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def page_password_tool():
    st.title("🔐 密碼工具")

    st.info("輸入密碼後，系統會產生對應的 password_hash，可直接貼回 users 表。")

    password = st.text_input("輸入密碼", type="password")

    if st.button("產生 password_hash", use_container_width=True):
        if not password:
            st.warning("請先輸入密碼。")
            return

        hashed = _hash_password(password)

        st.success("已產生 password_hash")
        st.code(hashed)

        st.caption("請將上方這一串複製到 users 分頁的 password_hash 欄位。")
