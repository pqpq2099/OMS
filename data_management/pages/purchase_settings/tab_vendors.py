from __future__ import annotations

from data_management.logic import logic_purchase_settings as purchase_logic
from .shared import _render_section_title, st


def _tab_vendors():
    _render_section_title("廠商管理", "先建立供應商，後面品項才能指定預設供應商。")

    show_inactive = False
    context = purchase_logic.build_vendor_context(show_inactive=show_inactive)

    col_left, col_right = st.columns([1.2, 1.8], gap="large")

    with col_left:
        mode = st.radio("操作模式", ["新增廠商", "編輯廠商"], horizontal=True, key="vendor_mode")

        if mode == "新增廠商":
            with st.form("form_create_vendor", clear_on_submit=True):
                vendor_name_zh = st.text_input("廠商名稱 *")
                vendor_name = st.text_input("系統名稱（英文/內部）")
                contact_name = st.text_input("聯絡人")
                phone = st.text_input("電話")
                line_id = st.text_input("LINE")
                notes = st.text_area("備註", height=80)
                is_active = st.toggle("啟用", value=True)
                brand_label = st.selectbox("品牌", options=context["brand_keys"], index=0 if context["brand_keys"] else None)

                submitted = st.form_submit_button("新增廠商", width="stretch")
                if submitted:
                    try:
                        purchase_logic.submit_create_vendor(
                            vendor_name_zh=vendor_name_zh,
                            vendor_name=vendor_name,
                            contact_name=contact_name,
                            phone=phone,
                            line_id=line_id,
                            notes=notes,
                            is_active=is_active,
                            brand_id=context["brand_map"].get(brand_label, ""),
                        )
                        st.success("廠商已新增")
                        st.rerun()
                    except purchase_logic.PurchaseServiceError as e:
                        st.error(str(e))
        else:
            vendor_label = st.selectbox(
                "選擇要編輯的廠商",
                options=list(context["vendor_options"].keys()),
                index=None,
                placeholder="請選擇廠商",
                key="edit_vendor_select",
            )
            if vendor_label:
                vendor_id = context["vendor_options"][vendor_label]
                edit_values = purchase_logic.get_vendor_edit_values(
                    context["vendors_df"], vendor_id, context["brand_map"]
                )
                with st.form("form_update_vendor"):
                    vendor_name_zh = st.text_input("廠商名稱 *", value=edit_values["vendor_name_zh"])
                    vendor_name = st.text_input("系統名稱（英文/內部）", value=edit_values["vendor_name"])
                    contact_name = st.text_input("聯絡人", value=edit_values["contact_name"])
                    phone = st.text_input("電話", value=edit_values["phone"])
                    line_id = st.text_input("LINE", value=edit_values["line_id"])
                    notes = st.text_area("備註", value=edit_values["notes"], height=80)
                    is_active = st.toggle("啟用", value=edit_values["is_active"])
                    brand_label = st.selectbox(
                        "品牌",
                        options=context["brand_keys"],
                        index=edit_values["brand_idx"] if context["brand_keys"] else None,
                    )
                    submitted = st.form_submit_button("更新廠商", width="stretch")
                    if submitted:
                        try:
                            purchase_logic.submit_update_vendor(
                                vendor_id=vendor_id,
                                vendor_name_zh=vendor_name_zh,
                                vendor_name=vendor_name,
                                contact_name=contact_name,
                                phone=phone,
                                line_id=line_id,
                                notes=notes,
                                is_active=is_active,
                                brand_id=context["brand_map"].get(brand_label, ""),
                            )
                            st.success("廠商已更新")
                            st.rerun()
                        except purchase_logic.PurchaseServiceError as e:
                            st.error(str(e))

    with col_right:
        st.markdown("**廠商列表**")
        show_inactive = st.checkbox("顯示停用廠商", value=False, key="show_inactive_vendors")
        display_context = purchase_logic.build_vendor_context(show_inactive=show_inactive)
        if display_context["display_df"].empty:
            st.info("目前沒有廠商資料")
        else:
            st.dataframe(display_context["display_df"], width="stretch", hide_index=True)
