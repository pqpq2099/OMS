from __future__ import annotations

from data_management.logic import logic_purchase_settings as purchase_logic
from .shared import _render_section_title, st


def _tab_units():
    _render_section_title("單位管理", "單位是全系統共用字典，不需先選供應商。")

    context = purchase_logic.build_unit_context(show_inactive=False)

    col_left, col_right = st.columns([1.1, 1.9], gap="large")

    with col_left:
        mode = st.radio("操作模式", ["新增單位", "編輯單位"], horizontal=True, key="unit_mode")

        if mode == "新增單位":
            with st.form("form_create_unit", clear_on_submit=True):
                unit_name_zh = st.text_input("單位名稱 *", help="例如：箱、包、kg、瓶")
                unit_name = st.text_input("系統名稱（英文/內部）")
                unit_symbol = st.text_input("顯示符號", help="例如：kg、g、L、ml")
                unit_type = st.text_input("單位類型", help="例如：count / weight / volume")
                is_active = st.toggle("啟用", value=True)
                brand_label = st.selectbox("品牌", options=context["brand_keys"], index=0 if context["brand_keys"] else None)
                submitted = st.form_submit_button("新增單位", width="stretch")
                if submitted:
                    try:
                        purchase_logic.submit_create_unit(
                            unit_name_zh=unit_name_zh,
                            unit_name=unit_name,
                            unit_symbol=unit_symbol,
                            unit_type=unit_type,
                            is_active=is_active,
                            brand_id=context["brand_map"].get(brand_label, ""),
                        )
                        st.success("單位已新增")
                        st.rerun()
                    except purchase_logic.PurchaseServiceError as e:
                        st.error(str(e))
        else:
            unit_label = st.selectbox(
                "選擇要編輯的單位",
                options=list(context["unit_options"].keys()),
                index=None,
                placeholder="請選擇單位",
                key="edit_unit_select",
            )
            if unit_label:
                unit_id = context["unit_options"][unit_label]
                edit_values = purchase_logic.get_unit_edit_values(context["units_df"], unit_id, context["brand_map"])
                with st.form("form_update_unit"):
                    unit_name_zh = st.text_input("單位名稱 *", value=edit_values["unit_name_zh"])
                    unit_name = st.text_input("系統名稱（英文/內部）", value=edit_values["unit_name"])
                    unit_symbol = st.text_input("顯示符號", value=edit_values["unit_symbol"])
                    unit_type = st.text_input("單位類型", value=edit_values["unit_type"])
                    is_active = st.toggle("啟用", value=edit_values["is_active"])
                    brand_label = st.selectbox(
                        "品牌",
                        options=context["brand_keys"],
                        index=edit_values["brand_idx"] if context["brand_keys"] else None,
                    )
                    submitted = st.form_submit_button("更新單位", width="stretch")
                    if submitted:
                        try:
                            purchase_logic.submit_update_unit(
                                unit_id=unit_id,
                                unit_name_zh=unit_name_zh,
                                unit_name=unit_name,
                                unit_symbol=unit_symbol,
                                unit_type=unit_type,
                                is_active=is_active,
                                brand_id=context["brand_map"].get(brand_label, ""),
                            )
                            st.success("單位已更新")
                            st.rerun()
                        except purchase_logic.PurchaseServiceError as e:
                            st.error(str(e))

    with col_right:
        st.markdown("**單位列表**")
        show_inactive = st.checkbox("顯示停用單位", value=False, key="show_inactive_units")
        display_context = purchase_logic.build_unit_context(show_inactive=show_inactive)
        if display_context["display_df"].empty:
            st.info("目前沒有單位資料")
        else:
            st.dataframe(display_context["display_df"], width="stretch", hide_index=True)
