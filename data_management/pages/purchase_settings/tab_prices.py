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
        unit_keys = list(context["unit_options"].keys())
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

    with col_right:
        st.markdown("**價格歷史**")
        if item_context["display_df"].empty:
            st.info("此品項目前沒有價格資料")
        else:
            st.dataframe(item_context["display_df"], width="stretch", hide_index=True)
            st.markdown("---")
            if st.button("↩️ 取消最新價格", use_container_width=True, key="btn_revert_price"):
                try:
                    purchase_logic.submit_revert_latest_price(item_id=item_id)
                    st.success("最新價格已取消，前一筆已還原")
                    st.rerun()
                except purchase_logic.PurchaseServiceError as e:
                    st.error(str(e))
