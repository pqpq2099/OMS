# ============================================================
# ORIVIA OMS - Store Pages
# 記憶對齊穩定版（手機欄寬修正版）
# ============================================================

from __future__ import annotations

from datetime import date
import pandas as pd
import streamlit as st

from oms_data import read_table


def _page_header(title: str, desc: str) -> None:
    st.title(title)
    st.caption(desc)
    st.divider()


def _safe_col(df: pd.DataFrame, col_name: str, default_value="") -> pd.Series:
    if col_name in df.columns:
        return df[col_name]
    return pd.Series([default_value] * len(df), index=df.index)


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _parse_unit_options(
    orderable_units_raw: str,
    default_order_unit: str,
    base_unit: str,
) -> list[str]:
    options: list[str] = []

    if orderable_units_raw:
        options = [u.strip() for u in str(orderable_units_raw).split(",") if u.strip()]

    if default_order_unit and default_order_unit not in options:
        options.insert(0, default_order_unit)

    if not options:
        fallback = default_order_unit or base_unit or ""
        options = [fallback]

    return options


def _get_item_display_name(row: pd.Series) -> str:
    item_name_zh = str(row.get("item_name_zh", "")).strip()
    item_name = str(row.get("item_name", "")).strip()
    item_id = str(row.get("item_id", "")).strip()

    if item_name_zh:
        return item_name_zh
    if item_name:
        return item_name
    return item_id


def _inject_fill_items_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1rem !important;
            padding-left: 0.55rem !important;
            padding-right: 0.55rem !important;
            max-width: 920px !important;
        }

        /* 主區 columns 維持橫向 */
        [data-testid="stHorizontalBlock"] {
            align-items: flex-start !important;
            gap: 0.28rem !important;
        }

        /* 舊版/新版 number_input +/- 全移除 */
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

        div[data-testid="stNumberInput"] {
            width: 100% !important;
        }

        div[data-testid="stNumberInput"] input {
            width: 100% !important;
            text-align: center !important;
            padding: 0.34rem 0.12rem !important;
            font-size: 0.95rem !important;
        }

        /* number_input 外框縮窄 */
        div[data-testid="stNumberInput"] > div {
            max-width: 4.4rem !important;
            min-width: 4.4rem !important;
        }

        /* Selectbox 壓縮 */
        div[data-testid="stSelectbox"] {
            width: 100% !important;
        }

        div[data-testid="stSelectbox"] > div {
            max-width: 4.2rem !important;
            min-width: 4.2rem !important;
        }

        div[data-testid="stSelectbox"] div[data-baseweb="select"] {
            min-height: 2.2rem !important;
        }

        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            min-height: 2.2rem !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            padding-left: 0.28rem !important;
            padding-right: 1.05rem !important;
            font-size: 0.92rem !important;
        }

        div[data-testid="stSelectbox"] svg {
            transform: scale(0.82) !important;
        }

        .vendor-title {
            font-size: 2.2rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 0.3rem;
        }

        .order-meta-line {
            font-size: 0.88rem;
            color: rgba(49,51,63,0.62);
            margin-top: 0.05rem;
            margin-bottom: 0.08rem;
        }

        .unit-inline {
            font-size: 0.95rem;
            font-weight: 600;
            padding-top: 0.32rem;
            white-space: nowrap;
            text-align: left;
        }

        .mobile-header-fix {
            font-size: 0.98rem;
            font-weight: 700;
            white-space: nowrap;
        }

        /* 手機版 */
        @media (max-width: 768px) {
            .block-container {
                padding-top: 0.65rem !important;
                padding-left: 0.36rem !important;
                padding-right: 0.36rem !important;
            }

            .vendor-title {
                font-size: 1.9rem !important;
                margin-bottom: 0.2rem !important;
            }

            .order-meta-line {
                font-size: 0.78rem !important;
                margin-bottom: 0.05rem !important;
            }

            .unit-inline {
                font-size: 0.84rem !important;
                padding-top: 0.38rem !important;
            }

            .mobile-header-fix {
                font-size: 0.88rem !important;
            }

            div[data-testid="stNumberInput"] input {
                font-size: 0.88rem !important;
                padding-top: 0.28rem !important;
                padding-bottom: 0.28rem !important;
                padding-left: 0.08rem !important;
                padding-right: 0.08rem !important;
            }

            /* 手機上只留夠 9.9 / 99 的寬度 */
            div[data-testid="stNumberInput"] > div {
                max-width: 3.6rem !important;
                min-width: 3.6rem !important;
            }

            /* 手機上單位更窄 */
            div[data-testid="stSelectbox"] > div {
                max-width: 3.25rem !important;
                min-width: 3.25rem !important;
            }

            div[data-testid="stSelectbox"] div[data-baseweb="select"] {
                min-height: 2.05rem !important;
            }

            div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
                min-height: 2.05rem !important;
                font-size: 0.84rem !important;
                padding-left: 0.12rem !important;
                padding-right: 0.92rem !important;
            }

            /* 降低欄間距，避免超出 */
            [data-testid="stHorizontalBlock"] {
                gap: 0.14rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_order_entry() -> None:
    _inject_fill_items_style()

    try:
        items = read_table("items")
        vendors = read_table("vendors")
        prices = read_table("prices")
    except Exception as e:
        st.error(f"讀取資料失敗：{e}")
        return

    if items is None or items.empty:
        st.warning("目前沒有 items 資料。")
        return

    items = items.copy()
    prices = prices.copy() if prices is not None else pd.DataFrame()

    required_item_cols = ["item_id", "default_vendor_id"]
    for col in required_item_cols:
        if col not in items.columns:
            st.error(f"items 缺少欄位：{col}")
            return

    items["item_name"] = _safe_col(items, "item_name", "")
    items["item_name_zh"] = _safe_col(items, "item_name_zh", "")
    items["base_unit"] = _safe_col(items, "base_unit", "")
    items["default_order_unit"] = _safe_col(items, "default_order_unit", "")
    items["default_stock_unit"] = _safe_col(items, "default_stock_unit", "")
    items["orderable_units"] = _safe_col(items, "orderable_units", "")
    items["default_vendor_id"] = items["default_vendor_id"].astype(str).str.strip()

    selected_vendor_name = str(st.session_state.get("vendor", "")).strip()

    if not selected_vendor_name and vendors is not None and not vendors.empty and "vendor_name" in vendors.columns:
        selected_vendor_name = str(vendors.iloc[0]["vendor_name"]).strip()

    if not selected_vendor_name:
        st.warning("目前沒有可用的廠商名稱。")
        return

    selected_vendor_id = ""
    if vendors is not None and not vendors.empty:
        vendors = vendors.copy()
        if {"vendor_id", "vendor_name"}.issubset(set(vendors.columns)):
            vendors["vendor_id"] = vendors["vendor_id"].astype(str).str.strip()
            vendors["vendor_name"] = vendors["vendor_name"].astype(str).str.strip()
            matched_vendor = vendors[vendors["vendor_name"] == selected_vendor_name]
            if not matched_vendor.empty:
                selected_vendor_id = str(matched_vendor.iloc[0]["vendor_id"]).strip()

    if selected_vendor_id:
        vendor_items = items[items["default_vendor_id"] == selected_vendor_id].copy()
    else:
        items["vendor_name"] = _safe_col(items, "vendor_name", "")
        items["vendor_name"] = items["vendor_name"].astype(str).str.strip()
        vendor_items = items[items["vendor_name"] == selected_vendor_name].copy()

    if vendor_items.empty:
        st.warning("此廠商目前沒有綁定品項。")
        return

    vendor_items["display_name"] = vendor_items.apply(_get_item_display_name, axis=1)
    vendor_items = vendor_items.sort_values("display_name").reset_index(drop=True)

    st.markdown(f'<div class="vendor-title">📝 {selected_vendor_name}</div>', unsafe_allow_html=True)

    with st.expander("📊 查看上次叫貨 / 期間消耗參考（已自動隱藏無紀錄品項）", expanded=False):
        st.caption("目前先保留區塊位置；之後再接歷史參考邏輯。")

    st.write("---")

    h1, h2, h3 = st.columns([5.9, 1.35, 1.35])
    with h1:
        st.markdown('<div class="mobile-header-fix">品項名稱（建議量 = 日均 × 1.5）</div>', unsafe_allow_html=True)
    with h2:
        st.markdown('<div class="mobile-header-fix" style="text-align:center;">庫</div>', unsafe_allow_html=True)
    with h3:
        st.markdown('<div class="mobile-header-fix" style="text-align:center;">進</div>', unsafe_allow_html=True)

    with st.form("inventory_form"):
        submit_rows = []
        last_item_display_name = ""

        for _, row in vendor_items.iterrows():
            item_id = str(row["item_id"]).strip()
            display_name = str(row["display_name"]).strip()
            base_unit = str(row["base_unit"]).strip()
            stock_unit = str(row["default_stock_unit"]).strip() or base_unit
            default_order_unit = str(row["default_order_unit"]).strip()
            orderable_units_raw = str(row["orderable_units"]).strip()

            order_unit_options = _parse_unit_options(
                orderable_units_raw=orderable_units_raw,
                default_order_unit=default_order_unit,
                base_unit=base_unit,
            )

            current_stock_qty = 0.0
            suggest_qty = 0.0

            price = 0.0
            if not prices.empty and {"item_id", "unit_price"}.issubset(set(prices.columns)):
                p_df = prices.copy()
                p_df["item_id"] = p_df["item_id"].astype(str).str.strip()
                p_df["unit_price"] = pd.to_numeric(p_df["unit_price"], errors="coerce").fillna(0)
                matched = p_df[p_df["item_id"] == item_id]
                if not matched.empty:
                    price = float(matched.iloc[-1]["unit_price"])

            c1, c2, c3 = st.columns([5.9, 1.35, 1.35])

            with c1:
                if display_name == last_item_display_name:
                    st.markdown(
                        f"<span style='color:gray;'>└ </span> <b>{stock_unit or '-'}</b>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f"**{display_name}**")

                st.markdown(
                    f'<div class="order-meta-line">總庫存：{current_stock_qty:.1f}　建議量：{suggest_qty:.1f}</div>',
                    unsafe_allow_html=True,
                )
                last_item_display_name = display_name

            with c2:
                stock_inline_cols = st.columns([1.55, 0.55])
                with stock_inline_cols[0]:
                    stock_qty = st.number_input(
                        "庫",
                        min_value=0.0,
                        step=0.1,
                        key=f"s_{item_id}",
                        format="%.1f",
                        value=0.0,
                        label_visibility="collapsed",
                    )
                with stock_inline_cols[1]:
                    st.markdown(
                        f'<div class="unit-inline">{stock_unit or "-"}</div>',
                        unsafe_allow_html=True,
                    )

            with c3:
                order_qty = st.number_input(
                    "進",
                    min_value=0.0,
                    step=0.1,
                    key=f"p_{item_id}",
                    format="%.1f",
                    value=0.0,
                    label_visibility="collapsed",
                )

                default_index = 0
                if default_order_unit in order_unit_options:
                    default_index = order_unit_options.index(default_order_unit)

                order_unit = st.selectbox(
                    f"{item_id}_unit",
                    options=order_unit_options,
                    index=default_index,
                    label_visibility="collapsed",
                    key=f"u_{item_id}",
                )

            submit_rows.append(
                {
                    "vendor_id": selected_vendor_id,
                    "vendor_name": selected_vendor_name,
                    "item_id": item_id,
                    "item_name": display_name,
                    "stock_unit": stock_unit,
                    "base_unit": base_unit,
                    "stock_qty": _safe_float(stock_qty),
                    "order_qty": _safe_float(order_qty),
                    "order_unit": order_unit,
                    "current_stock_qty": current_stock_qty,
                    "suggest_qty": suggest_qty,
                    "unit_price": price,
                    "record_date": str(date.today()),
                }
            )

        if st.form_submit_button("💾 儲存庫存並同步叫貨", use_container_width=True):
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
                        "vendor_name",
                        "item_id",
                        "item_name",
                        "current_stock_qty",
                        "suggest_qty",
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


def page_order_history() -> None:
    _page_header("叫貨紀錄", "查看歷史叫貨資料、廠商進貨內容與金額。")
    st.info("骨架版：此頁先保留位置，後續再接 purchase_orders / purchase_order_lines。")


def page_stocktake_history() -> None:
    _page_header("盤點歷史", "查看每次盤點前後的庫存變化與期間消耗。")
    st.info("骨架版：此頁先保留位置，後續再接 stocktakes / stocktake_lines。")
    st.write("上次庫存 + 期間進貨 - 這次庫存 = 期間消耗")
