from __future__ import annotations

from data_management.logic import logic_purchase_settings as purchase_logic
from .shared import _render_section_title, st


def _tab_prices():
    _render_section_title("價格管理", "先選供應商，再選該供應商底下的品項。")

    base_context = purchase_logic.build_price_context(vendor_id="")
    if base_context["vendors_df"].empty:
        st.info("請先建立啟用中的廠商")
        return

    selected_vendor_label = st.selectbox(
        "選擇供應商",
        options=list(base_context["vendor_options"].keys()),
        index=0 if base_context["vendor_options"] else None,
        key="price_vendor_select",
    )
    selected_vendor_id = base_context["vendor_options"].get(selected_vendor_label, "")
    context = purchase_logic.build_price_context(vendor_id=selected_vendor_id)

    if not context["item_options"]:
        st.info("此供應商目前沒有啟用品項")
        return

    selected_label = st.selectbox("選擇品項", options=list(context["item_options"].keys()), index=0, key="price_item_select")
    item_id = context["item_options"][selected_label]
    item_context = purchase_logic.build_price_item_context(item_id=item_id)

    col_left, col_right = st.columns([1.1, 1.9], gap="large")

    with col_left:
        mode = st.radio("操作模式", ["新增價格", "編輯價格"], horizontal=True, key="price_mode")
        unit_keys = list(context["unit_options"].keys())

        if mode == "新增價格":
            with st.form("form_create_price", clear_on_submit=True):
                unit_price = st.number_input("單價 *", min_value=0.0, step=0.1, format="%.1f")
                price_unit_label = st.selectbox("價格單位 *", options=unit_keys, index=None, placeholder="請選擇")
                effective_date = st.date_input("生效日期 *")
                is_active = st.toggle("啟用", value=True)
                submitted = st.form_submit_button("新增價格", width="stretch")
                if submitted:
                    try:
                        purchase_logic.submit_create_price(
                            item_id=item_id,
                            unit_price=unit_price,
                            price_unit=context["unit_options"].get(price_unit_label, ""),
                            effective_date=effective_date,
                            is_active=is_active,
                        )
                        st.success("價格已新增")
                        st.rerun()
                    except purchase_logic.PurchaseServiceError as e:
                        st.error(str(e))
        else:
            if item_context["prices_df"].empty:
                st.info("目前沒有可編輯的價格資料")
            else:
                selected_price_label = st.selectbox(
                    "選擇要編輯的價格",
                    options=list(item_context["price_options"].keys()),
                    index=0,
                    key="edit_price_select",
                )
                price_id = item_context["price_options"][selected_price_label]
                edit_values = purchase_logic.get_price_edit_values(
                    item_context["prices_df"], price_id, context["unit_options"]
                )
                with st.form("form_update_price"):
                    unit_price = st.number_input("單價 *", min_value=0.0, step=0.1, format="%.1f", value=edit_values["unit_price"])
                    price_unit_label = st.selectbox("價格單位 *", options=unit_keys, index=edit_values["price_unit_idx"])
                    effective_date = st.date_input("生效日期 *", value=edit_values["effective_date"])
                    end_date = st.text_input("結束日期（YYYY-MM-DD，可留空）", value=edit_values["end_date"])
                    is_active = st.toggle("啟用", value=edit_values["is_active"])
                    submitted = st.form_submit_button("更新價格", width="stretch")
                    if submitted:
                        try:
                            purchase_logic.submit_update_price(
                                price_id=price_id,
                                unit_price=unit_price,
                                price_unit=context["unit_options"].get(price_unit_label, ""),
                                effective_date=effective_date,
                                end_date=end_date,
                                is_active=is_active,
                            )
                            st.success("價格已更新")
                            st.rerun()
                        except purchase_logic.PurchaseServiceError as e:
                            st.error(str(e))

    with col_right:
        st.markdown("**價格歷史**")
        if item_context["display_df"].empty:
            st.info("此品項目前沒有價格資料")
        else:
            st.dataframe(item_context["display_df"], width="stretch", hide_index=True)
