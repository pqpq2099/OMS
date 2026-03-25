from __future__ import annotations

from data_management.logic import logic_purchase_settings as purchase_logic
from .shared import _render_section_title, st


def _tab_unit_conversions():
    _render_section_title("單位換算", "先選供應商，再選品項。填寫方式：請填大單位 → 小單位，例如：1箱 = 8包。")

    base_context = purchase_logic.build_unit_conversion_context(vendor_id="")
    if base_context["vendors_df"].empty:
        st.info("請先建立啟用中的廠商")
        return

    selected_vendor_label = st.selectbox(
        "選擇供應商",
        options=list(base_context["vendor_options"].keys()),
        index=0 if base_context["vendor_options"] else None,
        key="conv_vendor_select",
    )
    selected_vendor_id = base_context["vendor_options"].get(selected_vendor_label, "")
    context = purchase_logic.build_unit_conversion_context(vendor_id=selected_vendor_id)

    if not context["item_options"]:
        st.info("此供應商目前沒有啟用品項")
        return

    selected_item_label = st.selectbox("選擇品項", options=list(context["item_options"].keys()), index=0, key="conv_item_select")
    item_id = context["item_options"][selected_item_label]
    item_context = purchase_logic.build_conversion_item_context(item_id=item_id)

    col_left, col_right = st.columns([1.1, 1.9], gap="large")

    with col_left:
        mode = st.radio("操作模式", ["新增換算", "編輯換算"], horizontal=True, key="conv_mode")
        st.caption("請填「大單位 → 小單位」，例如：來源填箱、目標填包、比例填 8。")
        unit_keys = list(context["unit_options"].keys())

        if mode == "新增換算":
            with st.form("form_create_conversion", clear_on_submit=True):
                from_unit_label = st.selectbox("來源單位 *（通常填較大的單位，例如：箱）", options=unit_keys, index=None, placeholder="請選擇")
                ratio = st.number_input("比例 *（例如：1箱 = 8包，就填 8）", min_value=1, step=1, format="%d")
                to_unit_label = st.selectbox("目標單位 *（通常填較小的單位，例如：包）", options=unit_keys, index=None, placeholder="請選擇")
                is_active = st.toggle("啟用", value=True)
                submitted = st.form_submit_button("新增換算", width="stretch")
                if submitted:
                    try:
                        purchase_logic.submit_create_unit_conversion(
                            item_id=item_id,
                            from_unit=context["unit_options"].get(from_unit_label, ""),
                            to_unit=context["unit_options"].get(to_unit_label, ""),
                            ratio=ratio,
                            is_active=is_active,
                        )
                        st.success("換算已新增")
                        st.rerun()
                    except purchase_logic.PurchaseServiceError as e:
                        st.error(str(e))
        else:
            if item_context["conv_df"].empty:
                st.info("目前沒有可編輯的換算資料")
            else:
                selected_conv_label = st.selectbox(
                    "選擇要編輯的換算",
                    options=list(item_context["conversion_options"].keys()),
                    index=0,
                    key="edit_conv_select",
                )
                conversion_id = item_context["conversion_options"][selected_conv_label]
                edit_values = purchase_logic.get_conversion_edit_values(
                    item_context["conv_df"], conversion_id, context["unit_options"]
                )
                with st.form("form_update_conversion"):
                    from_unit_label = st.selectbox("來源單位 *（通常填較大的單位，例如：箱）", options=unit_keys, index=edit_values["from_unit_idx"])
                    ratio = st.number_input("比例 *（例如：1箱 = 8包，就填 8）", min_value=1, step=1, format="%d", value=edit_values["ratio"])
                    to_unit_label = st.selectbox("目標單位 *（通常填較小的單位，例如：包）", options=unit_keys, index=edit_values["to_unit_idx"])
                    is_active = st.toggle("啟用", value=edit_values["is_active"])
                    submitted = st.form_submit_button("更新換算", width="stretch")
                    if submitted:
                        try:
                            purchase_logic.submit_update_unit_conversion(
                                conversion_id=conversion_id,
                                from_unit=context["unit_options"].get(from_unit_label, ""),
                                to_unit=context["unit_options"].get(to_unit_label, ""),
                                ratio=ratio,
                                is_active=is_active,
                            )
                            st.success("換算已更新")
                            st.rerun()
                        except purchase_logic.PurchaseServiceError as e:
                            st.error(str(e))

    with col_right:
        st.markdown("**換算列表**")
        if item_context["display_df"].empty:
            st.info("此品項目前沒有單位換算資料")
        else:
            st.dataframe(item_context["display_df"], width="stretch", hide_index=True)
