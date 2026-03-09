# ============================================================
# ORIVIA OMS - Store Pages
# 簡潔表格式穩定版（依示意圖 2:1:1）
# ============================================================

from __future__ import annotations

import pandas as pd
import streamlit as st

from oms_data import read_table


# ============================================================
# Helpers
# ============================================================

def _page_header(title: str, desc: str) -> None:
    st.title(title)
    st.caption(desc)
    st.divider()


def _norm(v) -> str:
    if v is None:
        return ""
    text = str(v).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


def _safe_col(df: pd.DataFrame, col_name: str, default_value="") -> pd.Series:
    if col_name in df.columns:
        return df[col_name]
    return pd.Series([default_value] * len(df), index=df.index)


def _get_item_display_name(row: pd.Series) -> str:
    item_name_zh = _norm(row.get("item_name_zh", ""))
    item_name = _norm(row.get("item_name", ""))
    item_id = _norm(row.get("item_id", ""))

    if item_name_zh:
        return item_name_zh
    if item_name:
        return item_name
    return item_id


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


def _sort_items_for_operation(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    work = df.copy()
    work["_display_name"] = work.apply(_get_item_display_name, axis=1)

    if "display_order" in work.columns:
        work["_display_order_num"] = pd.to_numeric(
            work["display_order"], errors="coerce"
        ).fillna(999999)
        work = work.sort_values(
            ["_display_order_num", "_display_name"],
            ascending=[True, True],
        )
    else:
        work = work.sort_values(["_display_name"], ascending=[True])

    return work.reset_index(drop=True)


# ============================================================
# Style
# ============================================================

def _inject_order_page_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 0.8rem !important;
            padding-left: 0.35rem !important;
            padding-right: 0.35rem !important;
            max-width: 920px !important;
        }

        /* 移除 +/- */
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
            padding: 0.20rem 0.04rem !important;
            font-size: 0.92rem !important;
        }

        .vendor-title {
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.1;
            margin-top: 0.1rem;
            margin-bottom: 0.5rem;
            white-space: nowrap;
        }

        .section-line {
            margin: 10px 0 14px 0;
            border-top: 1px solid rgba(128,128,128,0.25);
        }

        .head-text {
            font-size: 0.98rem;
            font-weight: 700;
            white-space: nowrap;
        }

        .item-name {
            font-size: 1rem;
            font-weight: 700;
            line-height: 1.25;
            margin-bottom: 0.06rem;
            word-break: break-word;
        }

        .meta-line {
            font-size: 0.80rem;
            color: rgba(49, 51, 63, 0.82);
            line-height: 1.2;
            margin-top: 0.04rem;
            white-space: nowrap;
        }

        .unit-line {
            font-size: 0.85rem;
            color: rgba(49, 51, 63, 0.82);
            text-align: center;
            white-space: nowrap;
            margin-top: -0.1rem;
        }

        .row-gap {
            height: 0.15rem;
        }

        @media (max-width: 768px) {
            .block-container {
                padding-top: 0.6rem !important;
                padding-left: 0.22rem !important;
                padding-right: 0.22rem !important;
            }

            .vendor-title {
                font-size: 1.65rem !important;
            }

            .head-text {
                font-size: 0.88rem !important;
            }

            .item-name {
                font-size: 0.95rem !important;
            }

            .meta-line {
                font-size: 0.72rem !important;
            }

            .unit-line {
                font-size: 0.78rem !important;
            }

            div[data-testid="stNumberInput"] input {
                font-size: 0.86rem !important;
                padding: 0.16rem 0.03rem !important;
            }

            div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
                font-size: 0.80rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# Main Page
# ============================================================

def page_order_entry() -> None:
    _inject_order_page_style()

    items_df = read_table("items")
    vendors_df = read_table("vendors")

    if items_df is None or items_df.empty:
        st.warning("⚠️ 品項資料讀取失敗")
        return

    items_df = items_df.copy()

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

    selected_vendor_name = _norm(st.session_state.get("vendor_name", ""))
    if not selected_vendor_name:
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

    st.markdown(
        f"<div class='vendor-title'>📝 {selected_vendor_name}</div>",
        unsafe_allow_html=True,
    )

    with st.expander("📊 查看上次叫貨 / 期間消耗參考（已自動隱藏無紀錄品項）", expanded=False):
        st.caption("目前先保留區塊位置；之後再接歷史參考邏輯。")

    st.markdown("<div class='section-line'></div>", unsafe_allow_html=True)

    # 表頭：固定同一行 2:1:1
    h1, h2, h3 = st.columns([2, 1, 1], gap="small")
    with h1:
        st.markdown("<div class='head-text'>品項名稱（建議量=日均×1.5）</div>", unsafe_allow_html=True)
    with h2:
        st.markdown("<div class='head-text' style='text-align:center;'>庫</div>", unsafe_allow_html=True)
    with h3:
        st.markdown("<div class='head-text' style='text-align:center;'>進</div>", unsafe_allow_html=True)

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

            # 先用穩定版固定值，之後再接真資料
            total_stock_ref = 0.0
            suggest_qty = 0.0

            # 第 1 列：品項名稱 / 庫 / 進（同一行）
            r1c1, r1c2, r1c3 = st.columns([2, 1, 1], gap="small")
            with r1c1:
                st.markdown(f"<div class='item-name'>{item_name}</div>", unsafe_allow_html=True)
            with r1c2:
                st.write("")
            with r1c3:
                st.write("")

            # 第 2 列：名稱下方資訊 / 庫存輸入 / 進貨輸入
            r2c1, r2c2, r2c3 = st.columns([2, 1, 1], gap="small")
            with r2c1:
                st.markdown(
                    f"<div class='meta-line'>總庫存：{total_stock_ref:.1f} 建議量：{suggest_qty:.1f}</div>",
                    unsafe_allow_html=True,
                )
            with r2c2:
                stock_input = st.number_input(
                    "庫",
                    min_value=0.0,
                    step=0.1,
                    format="%.1f",
                    value=0.0,
                    key=f"stock_{item_id}",
                    label_visibility="collapsed",
                )
            with r2c3:
                order_input = st.number_input(
                    "進",
                    min_value=0.0,
                    step=0.1,
                    format="%.1f",
                    value=0.0,
                    key=f"order_{item_id}",
                    label_visibility="collapsed",
                )

            # 第 3 列：空 / 固定單位 / 下拉單位
            r3c1, r3c2, r3c3 = st.columns([2, 1, 1], gap="small")
            with r3c1:
                st.write("")
            with r3c2:
                st.markdown(f"<div class='unit-line'>{stock_unit or '-'}</div>", unsafe_allow_html=True)
            with r3c3:
                selected_order_unit = st.selectbox(
                    "進貨單位",
                    options=orderable_unit_options,
                    index=orderable_unit_options.index(order_unit) if order_unit in orderable_unit_options else 0,
                    key=f"order_unit_{item_id}",
                    label_visibility="collapsed",
                )

            st.markdown("<div class='row-gap'></div>", unsafe_allow_html=True)

            submit_rows.append(
                {
                    "item_id": item_id,
                    "item_name": item_name,
                    "stock_qty": float(stock_input),
                    "stock_unit": stock_unit,
                    "order_qty": float(order_input),
                    "order_unit": selected_order_unit,
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
        st.dataframe(result_df, use_container_width=True, hide_index=True)

    st.button(
        "⬅️ 返回功能選單",
        on_click=lambda: st.session_state.update(step="select_vendor"),
        use_container_width=True,
        key="back_from_order_entry",
    )


# ============================================================
# Other Pages
# ============================================================

def page_order_history() -> None:
    _page_header("叫貨紀錄", "查看歷史叫貨資料、廠商進貨內容與金額。")
    st.info("骨架版：此頁先保留位置，後續再接 purchase_orders / purchase_order_lines。")


def page_stocktake_history() -> None:
    _page_header("盤點歷史", "查看每次盤點前後的庫存變化與期間消耗。")
    st.info("骨架版：此頁先保留位置，後續再接 stocktakes / stocktake_lines。")
    st.write("上次庫存 + 期間進貨 - 這次庫存 = 期間消耗")
