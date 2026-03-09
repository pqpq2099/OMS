# ============================================================
# ORIVIA OMS - Store Pages
# 穩定版（避免手機 / 桌機跑版）
# ============================================================

from __future__ import annotations

import pandas as pd
import streamlit as st

from oms_data import read_table


# ============================================================
# Style（只控制輸入框，不碰整頁）
# ============================================================

def inject_style():

    st.markdown(
        """
<style>

.block-container{
    padding-top:1rem;
    padding-left:0.4rem;
    padding-right:0.4rem;
    max-width:900px;
}

/* 移除 +/- */
div[data-testid="stNumberInputStepUp"],
div[data-testid="stNumberInputStepDown"],
div[data-testid="stNumberInput"] button{
    display:none;
}

/* number input */

div[data-testid="stNumberInput"] input{
    text-align:center;
    padding:0.25rem;
}

/* 數字框寬度 */

div[data-testid="stNumberInput"] > div{
    width:70px;
}

/* selectbox */

div[data-testid="stSelectbox"] > div{
    width:80px;
}

div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
    font-size:0.9rem;
}

/* meta */

.order-meta{
    font-size:0.8rem;
    color:#666;
}

</style>
""",
        unsafe_allow_html=True,
    )


# ============================================================
# Helper
# ============================================================

def norm(v):
    if v is None:
        return ""
    return str(v).strip()


def safe_float(v):
    try:
        return float(v)
    except:
        return 0.0


def parse_units(raw, default_unit, base_unit):

    units = []

    if raw:
        units = [u.strip() for u in raw.split(",") if u.strip()]

    if default_unit and default_unit not in units:
        units.insert(0, default_unit)

    if not units:
        units = [default_unit or base_unit]

    return units


def item_display(row):

    zh = norm(row.get("item_name_zh"))
    en = norm(row.get("item_name"))

    if zh:
        return zh

    if en:
        return en

    return norm(row.get("item_id"))


# ============================================================
# Page
# ============================================================

def page_order_entry():

    inject_style()

    items = read_table("items")
    vendors = read_table("vendors")
    prices = read_table("prices")

    if items is None or items.empty:
        st.warning("items 無資料")
        return

    vendor_name = norm(st.session_state.get("vendor"))
    vendor_id = norm(st.session_state.get("vendor_id"))

    if not vendor_name and vendors is not None and not vendors.empty:
        vendor_name = vendors.iloc[0]["vendor_name"]

    if not vendor_id and vendors is not None:

        v = vendors[vendors["vendor_name"] == vendor_name]

        if not v.empty:
            vendor_id = v.iloc[0]["vendor_id"]

    vendor_items = items[
        items["default_vendor_id"].astype(str).str.strip() == vendor_id
    ].copy()

    if vendor_items.empty:
        st.warning("此廠商沒有品項")
        return

    vendor_items["display"] = vendor_items.apply(item_display, axis=1)

    vendor_items = vendor_items.sort_values("display")

    st.title(f"📝 {vendor_name}")

    st.write("---")

    head1, head2 = st.columns([5,2])

    with head1:
        st.write("**品項名稱（建議量 = 日均 × 1.5）**")

    with head2:
        st.write("**庫 / 進**")

    with st.form("order_form"):

        rows = []

        for _, row in vendor_items.iterrows():

            item_id = norm(row["item_id"])
            name = norm(row["display"])

            base_unit = norm(row.get("base_unit"))
            stock_unit = norm(row.get("default_stock_unit")) or base_unit
            order_unit = norm(row.get("default_order_unit")) or base_unit

            units = parse_units(
                norm(row.get("orderable_units")),
                order_unit,
                base_unit,
            )

            c1, c2 = st.columns([5,2])

            with c1:

                st.write(f"**{name}**")

                st.markdown(
                    "<div class='order-meta'>總庫存：0.0　建議量：0.0</div>",
                    unsafe_allow_html=True,
                )

            with c2:

                s1, s2 = st.columns(2)

                with s1:

                    stock = st.number_input(
                        "庫",
                        min_value=0.0,
                        step=0.1,
                        format="%.1f",
                        key=f"s_{item_id}",
                        label_visibility="collapsed",
                    )

                    st.caption(stock_unit)

                with s2:

                    order = st.number_input(
                        "進",
                        min_value=0.0,
                        step=0.1,
                        format="%.1f",
                        key=f"o_{item_id}",
                        label_visibility="collapsed",
                    )

                    unit = st.selectbox(
                        "單位",
                        units,
                        key=f"u_{item_id}",
                        label_visibility="collapsed",
                    )

            rows.append(
                {
                    "item_id":item_id,
                    "item_name":name,
                    "stock":safe_float(stock),
                    "stock_unit":stock_unit,
                    "order":safe_float(order),
                    "order_unit":unit,
                }
            )

        submit = st.form_submit_button("💾 儲存並同步", use_container_width=True)

    if submit:

        df = pd.DataFrame(rows)

        df = df[(df.stock>0)|(df.order>0)]

        if df.empty:

            st.warning("沒有輸入資料")

            return

        st.success("提交成功（目前為預覽）")

        st.dataframe(df, use_container_width=True)


# ============================================================
# Other Pages
# ============================================================

def page_order_history():

    st.title("叫貨紀錄")

    st.info("未接資料")


def page_stocktake_history():

    st.title("盤點歷史")

    st.info("未接資料")

def _inject_fill_items_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1rem !important;
            padding-left: 0.45rem !important;
            padding-right: 0.45rem !important;
            max-width: 920px !important;
        }

        /* 移除 number input +/- */
        div[data-testid="stNumberInputStepUp"],
        div[data-testid="stNumberInputStepDown"],
        div[data-testid="stNumberInput"] button,
        button[aria-label="Increase value"],
        button[aria-label="Decrease value"],
        button[aria-label*="Increase"],
        button[aria-label*="Decrease"] {
            display: none !important;
            width: 0 !important;
            min-width: 0 !important;
            max-width: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            border: 0 !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }

        input[type=number] {
            -moz-appearance: textfield !important;
            -webkit-appearance: none !important;
            appearance: textfield !important;
            margin: 0 !important;
        }

        div[data-testid="stNumberInput"] label {
            display: none !important;
        }

        div[data-testid="stNumberInput"] input {
            text-align: center !important;
            padding: 0.32rem 0.10rem !important;
            font-size: 0.95rem !important;
        }

        /* 輸入框寬度：夠 9.9 / 99 */
        div[data-testid="stNumberInput"] > div {
            width: 4.3rem !important;
            min-width: 4.3rem !important;
            max-width: 4.3rem !important;
        }

        /* 下拉要看得到文字 */
        div[data-testid="stSelectbox"] > div {
            width: 4.8rem !important;
            min-width: 4.8rem !important;
            max-width: 4.8rem !important;
        }

        div[data-testid="stSelectbox"] div[data-baseweb="select"] {
            min-height: 2.2rem !important;
        }

        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            min-height: 2.2rem !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            padding-left: 0.30rem !important;
            padding-right: 1.05rem !important;
            font-size: 0.92rem !important;
            white-space: nowrap !important;
            overflow: hidden !important;
        }

        div[data-testid="stSelectbox"] svg {
            transform: scale(0.82) !important;
        }

        .order-divider {
            margin: 10px 0 14px 0;
            border-top: 1px solid rgba(128,128,128,0.25);
        }

        .order-meta {
            font-size: 0.82rem;
            color: rgba(49, 51, 63, 0.82);
            margin-top: -0.15rem;
            margin-bottom: 0.2rem;
        }

        .order-head {
            font-size: 0.98rem;
            font-weight: 700;
            white-space: nowrap;
        }

        .order-item {
            padding: 0.15rem 0 0.35rem 0;
        }

        .unit-text {
            font-size: 0.86rem;
            color: rgba(49, 51, 63, 0.78);
            margin-top: 0.12rem;
        }

        @media (max-width: 768px) {
            .block-container {
                padding-top: 0.8rem !important;
                padding-left: 0.25rem !important;
                padding-right: 0.25rem !important;
            }

            .order-head {
                font-size: 0.9rem !important;
            }

            .order-meta {
                font-size: 0.76rem !important;
            }

            div[data-testid="stNumberInput"] input {
                font-size: 0.88rem !important;
                padding: 0.26rem 0.06rem !important;
            }

            div[data-testid="stNumberInput"] > div {
                width: 3.8rem !important;
                min-width: 3.8rem !important;
                max-width: 3.8rem !important;
            }

            div[data-testid="stSelectbox"] > div {
                width: 4.2rem !important;
                min-width: 4.2rem !important;
                max-width: 4.2rem !important;
            }

            div[data-testid="stSelectbox"] div[data-baseweb="select"] {
                min-height: 2.0rem !important;
            }

            div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
                min-height: 2.0rem !important;
                font-size: 0.84rem !important;
                padding-left: 0.18rem !important;
                padding-right: 0.90rem !important;
            }

            .unit-text {
                font-size: 0.78rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_order_entry() -> None:
    _inject_fill_items_style()

    items_df = read_table("items")
    vendors_df = read_table("vendors")
    prices_df = read_table("prices")

    if items_df is None or items_df.empty:
        st.warning("⚠️ 品項資料讀取失敗")
        return

    items_df = items_df.copy()
    prices_df = prices_df.copy() if prices_df is not None else pd.DataFrame()

    required_item_cols = ["item_id", "default_vendor_id"]
    for col in required_item_cols:
        if col not in items_df.columns:
            st.error(f"items 缺少欄位：{col}")
            return

    items_df["item_name"] = _safe_col(items_df, "item_name", "")
    items_df["item_name_zh"] = _safe_col(items_df, "item_name_zh", "")
    items_df["base_unit"] = _safe_col(items_df, "base_unit", "")
    items_df["default_order_unit"] = _safe_col(items_df, "default_order_unit", "")
    items_df["default_stock_unit"] = _safe_col(items_df, "default_stock_unit", "")
    items_df["orderable_units"] = _safe_col(items_df, "orderable_units", "")
    items_df["default_vendor_id"] = items_df["default_vendor_id"].astype(str).str.strip()

    selected_vendor_name = _norm(st.session_state.get("vendor", ""))
    selected_vendor_id = _norm(st.session_state.get("vendor_id", ""))

    if not selected_vendor_name and vendors_df is not None and not vendors_df.empty and "vendor_name" in vendors_df.columns:
        selected_vendor_name = _norm(vendors_df.iloc[0]["vendor_name"])

    if not selected_vendor_id and vendors_df is not None and not vendors_df.empty:
        vendors_work = vendors_df.copy()
        if {"vendor_id", "vendor_name"}.issubset(set(vendors_work.columns)):
            vendors_work["vendor_id"] = vendors_work["vendor_id"].astype(str).str.strip()
            vendors_work["vendor_name"] = vendors_work["vendor_name"].astype(str).str.strip()
            matched_vendor = vendors_work[vendors_work["vendor_name"] == selected_vendor_name]
            if not matched_vendor.empty:
                selected_vendor_id = _norm(matched_vendor.iloc[0]["vendor_id"])

    if not selected_vendor_name:
        st.warning("目前沒有可用的廠商名稱。")
        return

    vendor_items = items_df[
        items_df["default_vendor_id"].astype(str).str.strip() == selected_vendor_id
    ].copy()

    if vendor_items.empty:
        st.info("💡 此廠商目前沒有對應品項")
        st.button(
            "⬅️ 返回功能選單",
            on_click=lambda: st.session_state.update(step="select_vendor"),
            use_container_width=True,
            key="back_from_order_entry_empty",
        )
        return

    vendor_items = _sort_items_for_operation(vendor_items)

    st.title(f"📝 {selected_vendor_name}")

    with st.expander("📊 查看上次叫貨 / 期間消耗參考（已自動隱藏無紀錄品項）", expanded=False):
        st.caption("目前先保留區塊位置；之後再接歷史參考邏輯。")

    st.markdown("<div class='order-divider'></div>", unsafe_allow_html=True)

    head1, head2 = st.columns([6, 2])
    with head1:
        st.markdown("<div class='order-head'>品項名稱（建議量 = 日均 × 1.5）</div>", unsafe_allow_html=True)
    with head2:
        st.markdown("<div class='order-head' style='text-align:center;'>庫　進</div>", unsafe_allow_html=True)

    with st.form("order_entry_form"):
        submit_rows = []

        for _, row in vendor_items.iterrows():
            item_id = _norm(row.get("item_id", ""))
            item_name = _get_item_display_name(row)

            base_unit = _norm(row.get("base_unit", ""))
            stock_unit = _norm(row.get("default_stock_unit", "")) or base_unit
            order_unit = _norm(row.get("default_order_unit", "")) or base_unit

            orderable_units_raw = _norm(row.get("orderable_units", ""))
            orderable_unit_options = _parse_unit_options(
                orderable_units_raw=orderable_units_raw,
                default_order_unit=order_unit,
                base_unit=base_unit,
            )

            current_stock_qty = 0.0
            total_stock_ref = 0.0
            daily_avg = 0.0
            suggest_qty = round(daily_avg * 1.5, 1)
            status_hint = _status_hint(total_stock_ref, daily_avg, suggest_qty)

            price = 0.0
            if not prices_df.empty and {"item_id", "unit_price"}.issubset(set(prices_df.columns)):
                p_df = prices_df.copy()
                p_df["item_id"] = p_df["item_id"].astype(str).str.strip()
                p_df["unit_price"] = pd.to_numeric(p_df["unit_price"], errors="coerce").fillna(0)
                matched = p_df[p_df["item_id"] == item_id]
                if not matched.empty:
                    price = float(matched.iloc[-1]["unit_price"])

            row_left, row_right = st.columns([6, 2])

            with row_left:
                st.markdown(f"<div class='order-item'><b>{item_name}</b></div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div class='order-meta'>總庫存：{total_stock_ref:.1f}　建議量：{suggest_qty:.1f} {status_hint}</div>",
                    unsafe_allow_html=True,
                )

            with row_right:
                stock_col, order_col = st.columns(2)

                with stock_col:
                    stock_input = st.number_input(
                        "庫",
                        min_value=0.0,
                        step=0.1,
                        format="%.1f",
                        value=float(current_stock_qty),
                        key=f"stock_{item_id}",
                        label_visibility="collapsed",
                    )
                    st.markdown(
                        f"<div class='unit-text' style='text-align:center;'>{stock_unit or '-'}</div>",
                        unsafe_allow_html=True,
                    )

                with order_col:
                    order_input = st.number_input(
                        "進",
                        min_value=0.0,
                        step=0.1,
                        format="%.1f",
                        value=0.0,
                        key=f"order_{item_id}",
                        label_visibility="collapsed",
                    )
                    selected_order_unit = st.selectbox(
                        "進貨單位",
                        options=orderable_unit_options,
                        index=orderable_unit_options.index(order_unit) if order_unit in orderable_unit_options else 0,
                        key=f"order_unit_{item_id}",
                        label_visibility="collapsed",
                    )

            submit_rows.append(
                {
                    "item_id": item_id,
                    "item_name": item_name,
                    "stock_qty": float(stock_input),
                    "stock_unit": stock_unit,
                    "order_qty": float(order_input),
                    "order_unit": selected_order_unit,
                    "unit_price": price,
                }
            )

        submitted = st.form_submit_button("💾 儲存並同步", use_container_width=True)

    if submitted:
        result_df = pd.DataFrame(submit_rows)
        result_df = result_df[
            (result_df["stock_qty"] > 0) | (result_df["order_qty"] > 0)
        ].copy()

        if result_df.empty:
            st.warning("你還沒有輸入任何庫存或進貨數量。")
            return

        st.success("已完成提交預覽。這一版先不寫入資料庫，只先確認畫面與輸入流程。")
        st.dataframe(
            result_df[
                [
                    "item_id",
                    "item_name",
                    "stock_qty",
                    "stock_unit",
                    "order_qty",
                    "order_unit",
                    "unit_price",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.caption("備註：Enter 自動跳下一格未放入這版，先以穩定畫面對齊為主。")

    st.button(
        "⬅️ 返回功能選單",
        on_click=lambda: st.session_state.update(step="select_vendor"),
        use_container_width=True,
        key="back_from_order_entry",
    )


def page_order_history() -> None:
    _page_header("叫貨紀錄", "查看歷史叫貨資料、廠商進貨內容與金額。")
    st.info("骨架版：此頁先保留位置，後續再接 purchase_orders / purchase_order_lines。")


def page_stocktake_history() -> None:
    _page_header("盤點歷史", "查看每次盤點前後的庫存變化與期間消耗。")
    st.info("骨架版：此頁先保留位置，後續再接 stocktakes / stocktake_lines。")
    st.write("上次庫存 + 期間進貨 - 這次庫存 = 期間消耗")

