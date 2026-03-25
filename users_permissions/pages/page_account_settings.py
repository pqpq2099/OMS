# ============================================================
# ORIVIA OMS
# 檔案：pages/page_account_settings.py
# 說明：個人帳號管理頁
# 功能：顯示目前登入者資訊、允許使用者自行修改密碼。
# 注意：這一頁只處理本人帳號，不處理他人帳號管理。
# ============================================================

from __future__ import annotations

import streamlit as st

from users_permissions.services.service_users import (
    UserServiceError,
    build_account_info_df,
    get_user_row,
    norm_text,
)
from users_permissions.logic.user_write import change_my_password


def page_account_settings():
    st.title("🙍 個人帳號管理")

    login_user_id = norm_text(st.session_state.get("login_user", ""))
    if not login_user_id:
        st.warning("請先登入。")
        return

    try:
        user_row = get_user_row(login_user_id)
    except UserServiceError as e:
        st.error(str(e))
        return
    except Exception as e:
        st.error(f"讀取失敗：{e}")
        return

    st.markdown("### 目前帳號資訊")
    st.table(build_account_info_df(user_row))

    st.markdown("### 修改自己的密碼")
    st.caption("密碼至少 6 碼。修改成功後，下次登入會直接使用新密碼。")

    with st.form("account_change_password_form"):
        current_password = st.text_input("目前密碼", type="password")
        new_password = st.text_input("新密碼", type="password")
        confirm_password = st.text_input("確認新密碼", type="password")
        submitted = st.form_submit_button("儲存新密碼", use_container_width=True)

        if submitted:
            try:
                result = change_my_password(
                    login_user_id,
                    current_password=current_password,
                    new_password=new_password,
                    confirm_password=confirm_password,
                )
                st.success(result.get("message") or "✅ 密碼已更新")
            except UserServiceError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"修改失敗：{e}")
