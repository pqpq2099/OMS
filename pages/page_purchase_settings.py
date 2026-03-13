"""
頁面模組：採購設定 / 資料管理。

目前版本先專注主資料管理：
1. 廠商管理
2. 品項管理
3. 價格管理
4. 單位管理
5. 單位換算

目前系統採 item-only 模型：
- 一個 item = 一個實際採購規格
- 規格直接寫在品項名稱中
- 不啟用 spec 邏輯
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from oms_core import _norm
from services.service_purchase import (
    PurchaseServiceError,
    create_item,
    create_price,
    create_unit,
    create_unit_conversion,
    create_vendor,
    get_brand_options,
    list_active_items,
    list_active_units,
    list_active_vendors,
    list_items,
    list_prices,
    list_unit_conversions,
    list_units,
    list_vendors,
    update_item,
    update_price,
    update_unit,
    update_unit_conversion,
    update_vendor,
)


# ============================================================
# [P1] 基本共用顯示
# ============================================================
def _bool_text(v) -> str:
    text = str(v).strip().lower()
    return "啟用" if text in {"true", "1", "yes", "y"} else "停用"


def _vendor_label(r: pd.Series) -> str:
    return _norm(r.get("vendor_name_zh")) or _norm(r.get("vendor_name"))

def _unit_label(r: pd.Series) -> str:
    return _norm(r.get("unit_name_zh")) or _norm(r.get("unit_name"))

def _item_label(r: pd.Series) -> str:
    return _norm(r.get("item_name_zh")) or _norm(r.get("item_name"))

def _render_section_title(title: str, help_text: str = ""):
    st.subheader(title)
    if help_text:
        st.caption(help_text)
        
def _fmt_price_1(v) -> str:
    try:
        return f"{float(v):.1f}"
    except Exception:
        return str(v)


def _fmt_ratio_int(v) -> str:
    try:
        return str(int(round(float(v))))
    except Exception:
        return str(v)

def _filter_items_by_vendor(items_df: pd.DataFrame, vendor_id: str) -> pd.DataFrame:
    if items_df.empty:
        return items_df.copy()
    if not _norm(vendor_id):
        return items_df.copy()
    if "default_vendor_id" not in items_df.columns:
        return items_df.copy()
    return items_df[items_df["default_vendor_id"].astype(str) == _norm(vendor_id)].copy()


# ============================================================
# [P2] 廠商管理
# ============================================================
def _tab_vendors():
    _render_section_title("廠商管理", "先建立供應商，後面品項才能指定預設供應商。")

    vendors_df = list_vendors()
    brand_options = get_brand_options()
    brand_map = {label: brand_id for label, brand_id in brand_options}
    vendor_options = {
        _vendor_label(r): _norm(r.get("vendor_id"))
        for _, r in vendors_df.iterrows()
    }

    col_left, col_right = st.columns([1.2, 1.8], gap="large")

    with col_left:
        mode = st.radio(
            "操作模式",
            ["新增廠商", "編輯廠商"],
            horizontal=True,
            key="vendor_mode",
        )

        if mode == "新增廠商":
            with st.form("form_create_vendor", clear_on_submit=True):
                vendor_name_zh = st.text_input("廠商名稱 *")
                vendor_name = st.text_input("系統名稱（英文/內部）")
                contact_name = st.text_input("聯絡人")
                phone = st.text_input("電話")
                line_id = st.text_input("LINE")
                notes = st.text_area("備註", height=80)
                is_active = st.toggle("啟用", value=True)
                brand_label = st.selectbox(
                    "品牌",
                    options=list(brand_map.keys()),
                    index=0 if brand_map else None,
                )

                submitted = st.form_submit_button("新增廠商", use_container_width=True)
                if submitted:
                    try:
                        create_vendor(
                            vendor_name_zh=vendor_name_zh,
                            vendor_name=vendor_name,
                            contact_name=contact_name,
                            phone=phone,
                            line_id=line_id,
                            notes=notes,
                            is_active=is_active,
                            brand_id=brand_map.get(brand_label, ""),
                        )
                        st.success("廠商已新增")
                        st.rerun()
                    except PurchaseServiceError as e:
                        st.error(str(e))

        else:
            vendor_label = st.selectbox(
                "選擇要編輯的廠商",
                options=list(vendor_options.keys()),
                index=None,
                placeholder="請選擇廠商",
                key="edit_vendor_select",
            )

            if vendor_label:
                vendor_id = vendor_options[vendor_label]
                row = vendors_df[vendors_df["vendor_id"].astype(str) == vendor_id].iloc[0]

                with st.form("form_update_vendor"):
                    vendor_name_zh = st.text_input("廠商名稱 *", value=_norm(row.get("vendor_name_zh")))
                    vendor_name = st.text_input("系統名稱（英文/內部）", value=_norm(row.get("vendor_name")))
                    contact_name = st.text_input("聯絡人", value=_norm(row.get("contact_name")))
                    phone = st.text_input("電話", value=_norm(row.get("phone")))
                    line_id = st.text_input("LINE", value=_norm(row.get("line_id")))
                    notes = st.text_area("備註", value=_norm(row.get("notes")), height=80)
                    is_active = st.toggle("啟用", value=_bool_text(row.get("is_active")) == "啟用")
                    current_brand = _norm(row.get("brand_id"))
                    brand_idx = 0
                    if brand_map:
                        brand_keys = list(brand_map.keys())
                        for i, label in enumerate(brand_keys):
                            if brand_map[label] == current_brand:
                                brand_idx = i
                                break
                    brand_label = st.selectbox(
                        "品牌",
                        options=list(brand_map.keys()),
                        index=brand_idx if brand_map else None,
                    )

                    submitted = st.form_submit_button("更新廠商", use_container_width=True)
                    if submitted:
                        try:
                            update_vendor(
                                vendor_id=vendor_id,
                                vendor_name_zh=vendor_name_zh,
                                vendor_name=vendor_name,
                                contact_name=contact_name,
                                phone=phone,
                                line_id=line_id,
                                notes=notes,
                                is_active=is_active,
                                brand_id=brand_map.get(brand_label, ""),
                            )
                            st.success("廠商已更新")
                            st.rerun()
                        except PurchaseServiceError as e:
                            st.error(str(e))

    with col_right:
        st.markdown("**廠商列表**")

        show_inactive = st.checkbox("顯示停用廠商", value=False, key="show_inactive_vendors")
        view_df = vendors_df.copy()
        if not show_inactive and "is_active" in view_df.columns:
            view_df = view_df[view_df["is_active"].astype(str).str.lower().isin(["true", "1", "yes", "y"])]

        if view_df.empty:
            st.info("目前沒有廠商資料")
        else:
            display = pd.DataFrame(
                {
                    "廠商名稱": view_df["vendor_name_zh"].replace("", pd.NA).fillna(view_df["vendor_name"]),
                    "聯絡人": view_df.get("contact_name", ""),
                    "電話": view_df.get("phone", ""),
                    "LINE": view_df.get("line_id", ""),
                    "狀態": view_df.get("is_active", "").apply(_bool_text),
                }
            )
            st.dataframe(display, use_container_width=True, hide_index=True)


# ============================================================
# [P3] 品項管理（先選廠商）
# ============================================================
def _tab_items():
    _render_section_title("品項管理", "先選供應商，再管理該供應商底下的品項。")

    items_df = list_items()
    vendors_df = list_active_vendors()
    units_df = list_active_units()
    brand_options = get_brand_options()

    if vendors_df.empty:
        st.info("請先建立啟用中的廠商")
        return

    vendor_options = {_vendor_label(r): _norm(r.get("vendor_id")) for _, r in vendors_df.iterrows()}
    unit_options = {_unit_label(r): _norm(r.get("unit_name_zh") or r.get("unit_name") or r.get("unit_id")) for _, r in units_df.iterrows()}
    brand_map = {label: brand_id for label, brand_id in brand_options}

    selected_vendor_label = st.selectbox(
        "選擇供應商",
        options=list(vendor_options.keys()),
        index=0 if vendor_options else None,
        key="item_vendor_select",
    )
    selected_vendor_id = vendor_options.get(selected_vendor_label, "")

    filtered_items_df = _filter_items_by_vendor(items_df, selected_vendor_id)
    item_options = {_item_label(r): _norm(r.get("item_id")) for _, r in filtered_items_df.iterrows()}

    col_left, col_right = st.columns([1.25, 1.75], gap="large")

    with col_left:
        mode = st.radio(
            "操作模式",
            ["新增品項", "編輯品項"],
            horizontal=True,
            key="item_mode",
        )

        if mode == "新增品項":
            with st.form("form_create_item", clear_on_submit=True):
                st.text_input("目前供應商", value=selected_vendor_label, disabled=True)
                item_name_zh = st.text_input("品項名稱 *", help="請直接寫完整採購規格，例如：青醬(1kg×8包/箱)")
                item_name = st.text_input("系統名稱（英文/內部）")
                category = st.text_input("分類")
                spec = st.text_area("規格說明 / 備註", height=70)

                brand_label = st.selectbox(
                    "品牌",
                    options=list(brand_map.keys()),
                    index=0 if brand_map else None,
                )

                st.markdown("**單位設定**")
                base_unit_label = st.selectbox("基準單位 *", options=list(unit_options.keys()), index=None, placeholder="請選擇")
                stock_unit_label = st.selectbox("庫存單位 *", options=list(unit_options.keys()), index=None, placeholder="請選擇")
                order_unit_label = st.selectbox("預設叫貨單位 *", options=list(unit_options.keys()), index=None, placeholder="請選擇")
                orderable_unit_labels = st.multiselect("可叫貨單位 *", options=list(unit_options.keys()))
                is_active = st.toggle("啟用", value=True)

                submitted = st.form_submit_button("新增品項", use_container_width=True)
                if submitted:
                    try:
                        create_item(
                            item_name_zh=item_name_zh,
                            item_name=item_name,
                            category=category,
                            spec=spec,
                            default_vendor_id=selected_vendor_id,
                            base_unit=unit_options.get(base_unit_label, ""),
                            default_stock_unit=unit_options.get(stock_unit_label, ""),
                            default_order_unit=unit_options.get(order_unit_label, ""),
                            orderable_units=[unit_options[x] for x in orderable_unit_labels],
                            is_active=is_active,
                            brand_id=brand_map.get(brand_label, ""),
                        )
                        st.success("品項已新增")
                        st.rerun()
                    except PurchaseServiceError as e:
                        st.error(str(e))

        else:
            if not item_options:
                st.info("此供應商目前沒有品項可編輯")
            else:
                item_label = st.selectbox(
                    "選擇要編輯的品項",
                    options=list(item_options.keys()),
                    index=None,
                    placeholder="請選擇品項",
                    key="edit_item_select",
                )

                if item_label:
                    item_id = item_options[item_label]
                    row = filtered_items_df[filtered_items_df["item_id"].astype(str) == item_id].iloc[0]

                    current_brand = _norm(row.get("brand_id"))
                    current_base_unit = _norm(row.get("base_unit"))
                    current_stock_unit = _norm(row.get("default_stock_unit"))
                    current_order_unit = _norm(row.get("default_order_unit"))
                    current_orderable = [x.strip() for x in _norm(row.get("orderable_units")).split(",") if x.strip()]

                    unit_keys = list(unit_options.keys())

                    def _find_unit_idx(target: str) -> int:
                        for i, label in enumerate(unit_keys):
                            if unit_options[label] == target:
                                return i
                        return 0

                    brand_keys = list(brand_map.keys())
                    brand_idx = 0
                    for i, label in enumerate(brand_keys):
                        if brand_map[label] == current_brand:
                            brand_idx = i
                            break

                    default_orderable = [label for label in unit_keys if unit_options[label] in current_orderable]

                    with st.form("form_update_item"):
                        st.text_input("目前供應商", value=selected_vendor_label, disabled=True)
                        item_name_zh = st.text_input("品項名稱 *", value=_norm(row.get("item_name_zh")))
                        item_name = st.text_input("系統名稱（英文/內部）", value=_norm(row.get("item_name")))
                        category = st.text_input("分類", value=_norm(row.get("category")))
                        spec = st.text_area("規格說明 / 備註", value=_norm(row.get("spec")), height=70)

                        brand_label = st.selectbox("品牌", options=brand_keys, index=brand_idx if brand_keys else None)

                        st.markdown("**單位設定**")
                        base_unit_label = st.selectbox("基準單位 *", options=unit_keys, index=_find_unit_idx(current_base_unit))
                        stock_unit_label = st.selectbox("庫存單位 *", options=unit_keys, index=_find_unit_idx(current_stock_unit))
                        order_unit_label = st.selectbox("預設叫貨單位 *", options=unit_keys, index=_find_unit_idx(current_order_unit))
                        orderable_unit_labels = st.multiselect("可叫貨單位 *", options=unit_keys, default=default_orderable)
                        is_active = st.toggle("啟用", value=_bool_text(row.get("is_active")) == "啟用")

                        submitted = st.form_submit_button("更新品項", use_container_width=True)
                        if submitted:
                            try:
                                update_item(
                                    item_id=item_id,
                                    item_name_zh=item_name_zh,
                                    item_name=item_name,
                                    category=category,
                                    spec=spec,
                                    default_vendor_id=selected_vendor_id,
                                    base_unit=unit_options.get(base_unit_label, ""),
                                    default_stock_unit=unit_options.get(stock_unit_label, ""),
                                    default_order_unit=unit_options.get(order_unit_label, ""),
                                    orderable_units=[unit_options[x] for x in orderable_unit_labels],
                                    is_active=is_active,
                                    brand_id=brand_map.get(brand_label, ""),
                                )
                                st.success("品項已更新")
                                st.rerun()
                            except PurchaseServiceError as e:
                                st.error(str(e))

    with col_right:
        st.markdown("**該供應商品項列表**")

        search_text = st.text_input("搜尋品項", key="item_search")
        show_inactive = st.checkbox("顯示停用品項", value=False, key="show_inactive_items")

        view_df = filtered_items_df.copy()
        if search_text.strip():
            keyword = search_text.strip().lower()
            view_df = view_df[
                view_df["item_name_zh"].astype(str).str.lower().str.contains(keyword, na=False)
                | view_df["item_name"].astype(str).str.lower().str.contains(keyword, na=False)
            ]

        if not show_inactive and "is_active" in view_df.columns:
            view_df = view_df[view_df["is_active"].astype(str).str.lower().isin(["true", "1", "yes", "y"])]

        if view_df.empty:
            st.info("目前沒有符合條件的品項")
        else:
            display = pd.DataFrame(
                {
                    "品項名稱": view_df["item_name_zh"].replace("", pd.NA).fillna(view_df["item_name"]),
                    "分類": view_df.get("category", ""),
                    "基準單位": view_df.get("base_unit", ""),
                    "庫存單位": view_df.get("default_stock_unit", ""),
                    "叫貨單位": view_df.get("default_order_unit", ""),
                    "可叫貨單位": view_df.get("orderable_units", ""),
                    "狀態": view_df.get("is_active", "").apply(_bool_text),
                }
            )
            st.dataframe(display, use_container_width=True, hide_index=True)


# ============================================================
# [P4] 價格管理（先選廠商）
# ============================================================
def _tab_prices():
    _render_section_title("價格管理", "先選供應商，再選該供應商底下的品項。")

    vendors_df = list_active_vendors()
    items_df = list_active_items()
    units_df = list_active_units()

    if vendors_df.empty:
        st.info("請先建立啟用中的廠商")
        return

    vendor_options = {_vendor_label(r): _norm(r.get("vendor_id")) for _, r in vendors_df.iterrows()}
    unit_options = {_unit_label(r): _norm(r.get("unit_name_zh") or r.get("unit_name") or r.get("unit_id")) for _, r in units_df.iterrows()}

    selected_vendor_label = st.selectbox(
        "選擇供應商",
        options=list(vendor_options.keys()),
        index=0 if vendor_options else None,
        key="price_vendor_select",
    )
    selected_vendor_id = vendor_options.get(selected_vendor_label, "")

    filtered_items_df = _filter_items_by_vendor(items_df, selected_vendor_id)
    item_options = {_item_label(r): _norm(r.get("item_id")) for _, r in filtered_items_df.iterrows()}

    if not item_options:
        st.info("此供應商目前沒有啟用品項")
        return

    selected_label = st.selectbox(
        "選擇品項",
        options=list(item_options.keys()),
        index=0,
        key="price_item_select",
    )
    item_id = item_options[selected_label]
    prices_df = list_prices(item_id=item_id)

    col_left, col_right = st.columns([1.1, 1.9], gap="large")

    with col_left:
        mode = st.radio("操作模式", ["新增價格", "編輯價格"], horizontal=True, key="price_mode")

        if mode == "新增價格":
            with st.form("form_create_price", clear_on_submit=True):
                unit_price = st.number_input("單價 *", min_value=0.0, step=0.1, format="%.1f")
                price_unit_label = st.selectbox("價格單位 *", options=list(unit_options.keys()), index=None, placeholder="請選擇")
                effective_date = st.date_input("生效日期 *")
                is_active = st.toggle("啟用", value=True)

                submitted = st.form_submit_button("新增價格", use_container_width=True)
                if submitted:
                    try:
                        create_price(
                            item_id=item_id,
                            unit_price=unit_price,
                            price_unit=unit_options.get(price_unit_label, ""),
                            effective_date=effective_date,
                            is_active=is_active,
                        )
                        st.success("價格已新增")
                        st.rerun()
                    except PurchaseServiceError as e:
                        st.error(str(e))
        else:
            if prices_df.empty:
                st.info("目前沒有可編輯的價格資料")
            else:
                price_options = {
                    f"{_norm(r.get('effective_date'))}｜{_fmt_price_1(r.get('unit_price'))}/{_norm(r.get('price_unit'))}": _norm(r.get("price_id"))
                    for _, r in prices_df.iterrows()
                }
                selected_price_label = st.selectbox(
                    "選擇要編輯的價格",
                    options=list(price_options.keys()),
                    index=0,
                    key="edit_price_select",
                )
                price_id = price_options[selected_price_label]
                row = prices_df[prices_df["price_id"].astype(str) == price_id].iloc[0]

                unit_keys = list(unit_options.keys())

                def _find_unit_idx(target: str) -> int:
                    for i, label in enumerate(unit_keys):
                        if unit_options[label] == target:
                            return i
                        return 0

                with st.form("form_update_price"):
                    unit_price = st.number_input(
                        "單價 *",
                        min_value=0.0,
                        step=0.1,
                        format="%.1f",
                        value=float(_norm(row.get("unit_price")) or 0),
                    )
                    price_unit_label = st.selectbox(
                        "價格單位 *",
                        options=unit_keys,
                        index=_find_unit_idx(_norm(row.get("price_unit"))),
                    )
                    effective_date = st.date_input("生效日期 *", value=pd.to_datetime(_norm(row.get("effective_date"))).date())
                    end_date_raw = _norm(row.get("end_date"))
                    end_date = st.text_input("結束日期（YYYY-MM-DD，可留空）", value=end_date_raw)
                    is_active = st.toggle("啟用", value=_bool_text(row.get("is_active")) == "啟用")

                    submitted = st.form_submit_button("更新價格", use_container_width=True)
                    if submitted:
                        try:
                            update_price(
                                price_id=price_id,
                                unit_price=unit_price,
                                price_unit=unit_options.get(price_unit_label, ""),
                                effective_date=effective_date,
                                end_date=end_date,
                                is_active=is_active,
                            )
                            st.success("價格已更新")
                            st.rerun()
                        except PurchaseServiceError as e:
                            st.error(str(e))

    with col_right:
        st.markdown("**價格歷史**")
        if prices_df.empty:
            st.info("此品項目前沒有價格資料")
        else:
            display = pd.DataFrame(
                {
                    "生效日期": prices_df.get("effective_date", ""),
                    "單價": prices_df.get("unit_price", ""),
                    "單位": prices_df.get("price_unit", ""),
                    "結束日期": prices_df.get("end_date", ""),
                    "狀態": prices_df.get("is_active", "").apply(_bool_text),
                }
            )
            st.dataframe(display, use_container_width=True, hide_index=True)


# ============================================================
# [P5] 單位管理（全系統共用）
# ============================================================
def _tab_units():
    _render_section_title("單位管理", "單位是全系統共用字典，不需先選供應商。")

    units_df = list_units()
    brand_options = get_brand_options()
    brand_map = {label: brand_id for label, brand_id in brand_options}

    unit_options = {_unit_label(r): _norm(r.get("unit_id")) for _, r in units_df.iterrows()}

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
                brand_label = st.selectbox(
                    "品牌",
                    options=list(brand_map.keys()),
                    index=0 if brand_map else None,
                )

                submitted = st.form_submit_button("新增單位", use_container_width=True)
                if submitted:
                    try:
                        create_unit(
                            unit_name_zh=unit_name_zh,
                            unit_name=unit_name,
                            unit_symbol=unit_symbol,
                            unit_type=unit_type,
                            is_active=is_active,
                            brand_id=brand_map.get(brand_label, ""),
                        )
                        st.success("單位已新增")
                        st.rerun()
                    except PurchaseServiceError as e:
                        st.error(str(e))
        else:
            unit_label = st.selectbox(
                "選擇要編輯的單位",
                options=list(unit_options.keys()),
                index=None,
                placeholder="請選擇單位",
                key="edit_unit_select",
            )

            if unit_label:
                unit_id = unit_options[unit_label]
                row = units_df[units_df["unit_id"].astype(str) == unit_id].iloc[0]

                current_brand = _norm(row.get("brand_id"))
                brand_keys = list(brand_map.keys())
                brand_idx = 0
                for i, label in enumerate(brand_keys):
                    if brand_map[label] == current_brand:
                        brand_idx = i
                        break

                with st.form("form_update_unit"):
                    unit_name_zh = st.text_input("單位名稱 *", value=_norm(row.get("unit_name_zh")))
                    unit_name = st.text_input("系統名稱（英文/內部）", value=_norm(row.get("unit_name")))
                    unit_symbol = st.text_input("顯示符號", value=_norm(row.get("unit_symbol")))
                    unit_type = st.text_input("單位類型", value=_norm(row.get("unit_type")))
                    is_active = st.toggle("啟用", value=_bool_text(row.get("is_active")) == "啟用")
                    brand_label = st.selectbox("品牌", options=brand_keys, index=brand_idx if brand_keys else None)

                    submitted = st.form_submit_button("更新單位", use_container_width=True)
                    if submitted:
                        try:
                            update_unit(
                                unit_id=unit_id,
                                unit_name_zh=unit_name_zh,
                                unit_name=unit_name,
                                unit_symbol=unit_symbol,
                                unit_type=unit_type,
                                is_active=is_active,
                                brand_id=brand_map.get(brand_label, ""),
                            )
                            st.success("單位已更新")
                            st.rerun()
                        except PurchaseServiceError as e:
                            st.error(str(e))

    with col_right:
        st.markdown("**單位列表**")
        show_inactive = st.checkbox("顯示停用單位", value=False, key="show_inactive_units")
        view_df = units_df.copy()
        if not show_inactive and "is_active" in view_df.columns:
            view_df = view_df[view_df["is_active"].astype(str).str.lower().isin(["true", "1", "yes", "y"])]

        if view_df.empty:
            st.info("目前沒有單位資料")
        else:
            display = pd.DataFrame(
                {
                    "單位名稱": view_df["unit_name_zh"].replace("", pd.NA).fillna(view_df["unit_name"]),
                    "符號": view_df.get("unit_symbol", ""),
                    "類型": view_df.get("unit_type", ""),
                    "狀態": view_df.get("is_active", "").apply(_bool_text),
                }
            )
            st.dataframe(display, use_container_width=True, hide_index=True)


# ============================================================
# [P6] 單位換算（先選廠商）
# ============================================================
def _tab_unit_conversions():
    _render_section_title("單位換算", "先選供應商，再選品項。填寫方式：請填大單位 → 小單位，例如：1箱 = 8包。")

    vendors_df = list_active_vendors()
    items_df = list_active_items()
    units_df = list_active_units()

    if vendors_df.empty:
        st.info("請先建立啟用中的廠商")
        return

    vendor_options = {_vendor_label(r): _norm(r.get("vendor_id")) for _, r in vendors_df.iterrows()}
    unit_options = {_unit_label(r): _norm(r.get("unit_name_zh") or r.get("unit_name") or r.get("unit_id")) for _, r in units_df.iterrows()}

    selected_vendor_label = st.selectbox(
        "選擇供應商",
        options=list(vendor_options.keys()),
        index=0 if vendor_options else None,
        key="conv_vendor_select",
    )
    selected_vendor_id = vendor_options.get(selected_vendor_label, "")

    filtered_items_df = _filter_items_by_vendor(items_df, selected_vendor_id)
    item_options = {_item_label(r): _norm(r.get("item_id")) for _, r in filtered_items_df.iterrows()}

    if not item_options:
        st.info("此供應商目前沒有啟用品項")
        return

    selected_item_label = st.selectbox(
        "選擇品項",
        options=list(item_options.keys()),
        index=0,
        key="conv_item_select",
    )
    item_id = item_options[selected_item_label]
    conv_df = list_unit_conversions(item_id=item_id)

    col_left, col_right = st.columns([1.1, 1.9], gap="large")

    with col_left:
        mode = st.radio("操作模式", ["新增換算", "編輯換算"], horizontal=True, key="conv_mode")
        st.caption("請填「大單位 → 小單位」，例如：來源填箱、目標填包、比例填 8。")

        if mode == "新增換算":
            with st.form("form_create_conversion", clear_on_submit=True):
                from_unit_label = st.selectbox(
                    "來源單位 *（通常填較大的單位，例如：箱）",
                    options=list(unit_options.keys()),
                    index=None,
                    placeholder="請選擇",
                )
                ratio = st.number_input("比例 *（例如：1箱 = 8包，就填 8）", min_value=1, step=1, format="%d")
                to_unit_label = st.selectbox(
                    "目標單位 *（通常填較小的單位，例如：包）",
                    options=list(unit_options.keys()),
                    index=None,
                    placeholder="請選擇",
                )
                is_active = st.toggle("啟用", value=True)

                submitted = st.form_submit_button("新增換算", use_container_width=True)
                if submitted:
                    try:
                        create_unit_conversion(
                            item_id=item_id,
                            from_unit=unit_options.get(from_unit_label, ""),
                            to_unit=unit_options.get(to_unit_label, ""),
                            ratio=ratio,
                            is_active=is_active,
                        )
                        st.success("換算已新增")
                        st.rerun()
                    except PurchaseServiceError as e:
                        st.error(str(e))
        else:
            if conv_df.empty:
                st.info("目前沒有可編輯的換算資料")
            else:
                conv_options = {
                    f"1{_norm(r.get('from_unit'))} = {_norm(r.get('ratio'))}{_norm(r.get('to_unit'))}｜{_norm(r.get('conversion_id'))}": _norm(r.get("conversion_id"))
                    for _, r in conv_df.iterrows()
                }
                selected_conv_label = st.selectbox(
                    "選擇要編輯的換算",
                    options=list(conv_options.keys()),
                    index=0,
                    key="edit_conv_select",
                )
                conversion_id = conv_options[selected_conv_label]
                row = conv_df[conv_df["conversion_id"].astype(str) == conversion_id].iloc[0]

                unit_keys = list(unit_options.keys())

                def _find_unit_idx(target: str) -> int:
                    for i, label in enumerate(unit_keys):
                        if unit_options[label] == target:
                            return i
                    return 0

                with st.form("form_update_conversion"):
                    from_unit_label = st.selectbox(
                        "來源單位 *（通常填較大的單位，例如：箱）",
                        options=unit_keys,
                        index=_find_unit_idx(_norm(row.get("from_unit"))),
                    )
                    ratio = st.number_input(
                        "比例 *（例如：1箱 = 8包，就填 8）",
                        min_value=1,
                        step=1,
                        format="%d",
                        value=int(round(float(_norm(row.get("ratio")) or 0))),
                    )
                    to_unit_label = st.selectbox(
                        "目標單位 *（通常填較小的單位，例如：包）",
                        options=unit_keys,
                        index=_find_unit_idx(_norm(row.get("to_unit"))),
                    )
                    is_active = st.toggle("啟用", value=_bool_text(row.get("is_active")) == "啟用")

                    submitted = st.form_submit_button("更新換算", use_container_width=True)
                    if submitted:
                        try:
                            update_unit_conversion(
                                conversion_id=conversion_id,
                                from_unit=unit_options.get(from_unit_label, ""),
                                to_unit=unit_options.get(to_unit_label, ""),
                                ratio=ratio,
                                is_active=is_active,
                            )
                            st.success("換算已更新")
                            st.rerun()
                        except PurchaseServiceError as e:
                            st.error(str(e))

    with col_right:
        st.markdown("**換算列表**")
        if conv_df.empty:
            st.info("此品項目前沒有單位換算資料")
        else:
            display = pd.DataFrame(
                {
                    "換算": conv_df.apply(
                        lambda r: f"1{_norm(r.get('from_unit'))} = {_norm(r.get('ratio'))}{_norm(r.get('to_unit'))}",
                        axis=1,
                    ),
                    "狀態": conv_df.get("is_active", "").apply(_bool_text),
                }
            )
            st.dataframe(display, use_container_width=True, hide_index=True)


# ============================================================
# [P7] 主頁入口
# ============================================================
def page_purchase_settings():
    st.title("🛒 採購設定")
    st.caption("目前先以 item-only 模型管理主資料：廠商、品項、價格、單位、單位換算。")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["廠商管理", "品項管理", "價格管理", "單位管理", "單位換算"]
    )

    with tab1:
        _tab_vendors()

    with tab2:
        _tab_items()

    with tab3:
        _tab_prices()

    with tab4:
        _tab_units()

    with tab5:
        _tab_unit_conversions()
