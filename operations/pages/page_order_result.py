from __future__ import annotations

from datetime import date

import streamlit as st

from shared.core.navigation import goto
from operations.logic import logic_order_result


def page_order_message_detail():
    st.title("🧾 叫貨明細")

    store_id = st.session_state.get("store_id", "")
    store_name = st.session_state.get("store_name", "")

    if not store_id:
        st.warning("請先選擇分店")
        return

    selected_date = st.date_input(
        "日期",
        value=date.today(),
        key="order_message_detail_date",
    )

    view_model = logic_order_result.build_order_message_detail_view_model(
        store_id=str(store_id).strip(),
        store_name=store_name,
        selected_date=selected_date,
    )
    status = view_model.get("status")
    if status == "error":
        st.error(view_model.get("message", "處理失敗"))
        return
    if status == "info":
        st.info(view_model.get("message", "目前沒有資料"))
        return

    line_message = view_model.get("line_message", "")

    st.markdown("### LINE 顯示內容")
    st.code(line_message, language="text")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("📤 發送到 LINE", type="primary", use_container_width=True):
            ok = logic_order_result.dispatch_line_message(
                line_message=line_message,
                store_id=str(store_id).strip(),
            )
            if ok:
                st.success("✅ 已成功發送到 LINE")
            else:
                st.error("❌ LINE 發送失敗，請檢查 line_bot / line_groups 設定")

    with c2:
        if st.button("⬅️ 返回功能選單", use_container_width=True, key="back_from_order_message_detail"):
            goto("select_vendor")
