from __future__ import annotations

from data_management.logic import logic_purchase_settings as purchase_logic
from .shared import _render_section_title, st


def _tab_items():
    _render_section_title("品項管理", "先選供應商，再管理該供應商底下的品項。")

    base_context = purchase_logic.build_item_context(vendor_id="", search_text="", show_inactive=False)
    if base_context["vendors_df"].empty:
        st.info("請先建立啟用中的廠商")
        return

    selected_vendor_label = st.selectbox(
        "選擇供應商",
        options=list(base_context["vendor_options"].keys()),
        index=0 if base_context["vendor_options"] else None,
        key="item_vendor_select",
    )
    selected_vendor_id = base_context["vendor_options"].get(selected_vendor_label, "")
    search_text = st.session_state.get("item_search", "")
    show_inactive = bool(st.session_state.get("show_inactive_items", False))
    context = purchase_logic.build_item_context(
        vendor_id=selected_vendor_id,
        search_text=search_text,
        show_inactive=show_inactive,
    )

    col_left, col_right = st.columns([1.25, 1.75], gap="large")

    with col_left:
        mode = st.radio("操作模式", ["新增品項", "編輯品項"], horizontal=True, key="item_mode")
        unit_keys = list(context["unit_options"].keys())

        if mode == "新增品項":
            with st.form("form_create_item", clear_on_submit=True):
                st.text_input("目前供應商", value=selected_vendor_label, disabled=True)
                item_name_zh = st.text_input("品項名稱 *", help="請直接寫完整採購規格，例如：青醬(1kg×8包/箱)")
                item_name = st.text_input("系統名稱（英文/內部）")
                category = st.text_input("分類")
                spec = st.text_area("規格說明 / 備註", height=70)
                brand_label = st.selectbox("品牌", options=context["brand_keys"], index=0 if context["brand_keys"] else None)
                st.markdown("**單位設定**")
                base_unit_label = st.selectbox("基準單位 *", options=unit_keys, index=None, placeholder="請選擇")
                stock_unit_label = st.selectbox("庫存單位 *", options=unit_keys, index=None, placeholder="請選擇")
                order_unit_label = st.selectbox("預設叫貨單位 *", options=unit_keys, index=None, placeholder="請選擇")
                orderable_unit_labels = st.multiselect("可叫貨單位 *", options=unit_keys)
                is_active = st.toggle("啟用", value=True)
                submitted = st.form_submit_button("新增品項", width="stretch")
                if submitted:
                    try:
                        purchase_logic.submit_create_item(
                            item_name_zh=item_name_zh,
                            item_name=item_name,
                            category=category,
                            spec=spec,
                            default_vendor_id=selected_vendor_id,
                            base_unit=context["unit_options"].get(base_unit_label, ""),
                            default_stock_unit=context["unit_options"].get(stock_unit_label, ""),
                            default_order_unit=context["unit_options"].get(order_unit_label, ""),
                            orderable_units=[context["unit_options"][x] for x in orderable_unit_labels],
                            is_active=is_active,
                            brand_id=context["brand_map"].get(brand_label, ""),
                        )
                        st.success("品項已新增")
                        st.rerun()
                    except purchase_logic.PurchaseServiceError as e:
                        st.error(str(e))
        else:
            if not context["item_options"]:
                st.info("此供應商目前沒有品項可編輯")
            else:
                item_label = st.selectbox(
                    "選擇要編輯的品項",
                    options=list(context["item_options"].keys()),
                    index=None,
                    placeholder="請選擇品項",
                    key="edit_item_select",
                )
                if item_label:
                    item_id = context["item_options"][item_label]
                    edit_values = purchase_logic.get_item_edit_values(
                        context["filtered_items_df"], item_id, context["brand_map"], context["unit_options"]
                    )
                    with st.form("form_update_item"):
                        st.text_input("目前供應商", value=selected_vendor_label, disabled=True)
                        item_name_zh = st.text_input("品項名稱 *", value=edit_values["item_name_zh"])
                        item_name = st.text_input("系統名稱（英文/內部）", value=edit_values["item_name"])
                        category = st.text_input("分類", value=edit_values["category"])
                        spec = st.text_area("規格說明 / 備註", value=edit_values["spec"], height=70)
                        brand_label = st.selectbox(
                            "品牌",
                            options=context["brand_keys"],
                            index=edit_values["brand_idx"] if context["brand_keys"] else None,
                        )
                        st.markdown("**單位設定**")
                        base_unit_label = st.selectbox("基準單位 *", options=unit_keys, index=edit_values["base_unit_idx"])
                        stock_unit_label = st.selectbox("庫存單位 *", options=unit_keys, index=edit_values["stock_unit_idx"])
                        order_unit_label = st.selectbox("預設叫貨單位 *", options=unit_keys, index=edit_values["order_unit_idx"])
                        orderable_unit_labels = st.multiselect("可叫貨單位 *", options=unit_keys, default=edit_values["default_orderable"])
                        is_active = st.toggle("啟用", value=edit_values["is_active"])
                        submitted = st.form_submit_button("更新品項", width="stretch")
                        if submitted:
                            try:
                                purchase_logic.submit_update_item(
                                    item_id=item_id,
                                    item_name_zh=item_name_zh,
                                    item_name=item_name,
                                    category=category,
                                    spec=spec,
                                    default_vendor_id=selected_vendor_id,
                                    base_unit=context["unit_options"].get(base_unit_label, ""),
                                    default_stock_unit=context["unit_options"].get(stock_unit_label, ""),
                                    default_order_unit=context["unit_options"].get(order_unit_label, ""),
                                    orderable_units=[context["unit_options"][x] for x in orderable_unit_labels],
                                    is_active=is_active,
                                    brand_id=context["brand_map"].get(brand_label, ""),
                                )
                                st.success("品項已更新")
                                st.rerun()
                            except purchase_logic.PurchaseServiceError as e:
                                st.error(str(e))

    with col_right:
        st.markdown("**該供應商品項列表**")
        search_text = st.text_input("搜尋品項", key="item_search")
        show_inactive = st.checkbox("顯示停用品項", value=False, key="show_inactive_items")
        display_context = purchase_logic.build_item_context(
            vendor_id=selected_vendor_id,
            search_text=search_text,
            show_inactive=show_inactive,
        )
        if display_context["display_df"].empty:
            st.info("目前沒有符合條件的品項")
        else:
            st.dataframe(display_context["display_df"], width="stretch", hide_index=True)
