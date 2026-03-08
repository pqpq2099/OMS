# ============================================================
# ORIVIA OMS - Store Pages
# 回接 1.0 版型重建版
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
            padding-top: 2rem !important;
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
            max-width: 900px !important;
        }

        /* 移除 number_input +/- */
        div[data-testid="stNumberInputStepUp"],
        div[data-testid="stNumberInputStepDown"] {
            display: none !important;
        }

        input[type=number] {
            -moz-appearance: textfield !important;
            -webkit-appearance: none !important;
            margin: 0 !important;
        }

        /* 讓 row 維持橫向 */
        [data-testid="stHorizontalBlock"] {
            align-items: start !important;
        }

        /* 壓縮數字框 */
        div[data-testid="stNumberInput"] input {
            text-align: center !important;
        }

        /* 標題區更像 1.0 */
        .vendor-title {
            font-size: 2.6rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 0.5rem;
        }

        .item-caption {
            font-size: 0.95rem;
            color: rgba(49,51,63,0.65);
            margin-top: 0.1rem;
            margin-bottom: 0.2rem;
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

    if vendors is None or vendors.empty:
        st.warning("目前沒有 vendors 資料。")
        return

    items = items.copy()
    vendors = vendors.copy()
    prices = prices.copy() if prices is not None else pd.DataFrame()

    required_vendor_cols = ["vendor_id", "vendor_name"]
    required_item_cols = ["item_id", "default_vendor_id"]

    for col in required_vendor_cols:
        if col not in vendors.columns:
            st.error(f"vendors 缺少欄位：{col}")
            return

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

    vendor_options = vendors[["vendor_id", "vendor_name"]].copy()
    vendor_options["vendor_id"] = vendor_options["vendor_id"].astype(str).str.strip()
    vendor_options["vendor_name"] = vendor_options["vendor_name"].astype(str).str.strip()
    vendor_options = vendor_options[vendor_options["vendor_name"] != ""]

    if vendor_options.empty:
        st.warning("vendors 有資料，但沒有可用的 vendor_name。")
        return

    selected_vendor_name = st.selectbox(
        "選擇廠商",
        options=vendor_options["vendor_name"].tolist(),
        index=0,
    )

    selected_vendor_row = vendor_options[
        vendor_options["vendor_name"] == selected_vendor_name
    ].iloc[0]
    selected_vendor_id = str(selected_vendor_row["vendor_id"]).strip()

    vendor_items = items[items["default_vendor_id"] == selected_vendor_id].copy()

    if vendor_items.empty:
        st.warning("此廠商目前沒有綁定品項。")
        return

    vendor_items["display_name"] = vendor_items.apply(_get_item_display_name, axis=1)

    # 先做排序，讓畫面更接近舊版操作感
    vendor_items = vendor_items.sort_values("display_name").reset_index(drop=True)

    # 標題區：接近舊版
    st.markdown(f'<div class="vendor-title">📝 {selected_vendor_name}</div>', unsafe_allow_html=True)

    with st.expander("📊 查看上次叫貨 / 庫存參考（已自動隱藏無紀錄品項）", expanded=False):
        st.caption("目前先保留區塊位置；之後再接歷史參考邏輯。")

    st.write("---")

    h1, h2, h3 = st.columns([6, 1, 1])
    with h1:
        st.markdown("**品項名稱**")
    with h2:
        st.markdown("<div style='text-align:center;'><b>庫</b></div>", unsafe_allow_html=True)
    with h3:
        st.markdown("<div style='text-align:center;'><b>進</b></div>", unsafe_allow_html=True)

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

            # 先用占位資料，避免又被其他表結構拖垮
            previous_stock = 0.0
            previous_order = 0.0
            avg_usage = 0.0
            suggest_qty = 0.0

            # 若 prices 表存在且有基本欄位，先抓單價；沒有就 0
            price = 0.0
            if not prices.empty and {"item_id", "unit_price"}.issubset(set(prices.columns)):
                p_df = prices.copy()
                p_df["item_id"] = p_df["item_id"].astype(str).str.strip()
                p_df["unit_price"] = pd.to_numeric(p_df["unit_price"], errors="coerce").fillna(0)
                matched = p_df[p_df["item_id"] == item_id]
                if not matched.empty:
                    price = float(matched.iloc[-1]["unit_price"])

            c1, c2, c3 = st.columns([6, 1, 1])

            with c1:
                if display_name == last_item_display_name:
                    st.markdown(f"<span style='color:gray;'>└ </span> <b>{stock_unit or '-'}</b>", unsafe_allow_html=True)
                else:
                    st.markdown(f"**{display_name}**")

                st.caption(
                    f"{stock_unit or '-'} (前結:{previous_stock:.1f} | 單價:{price:.1f} | 💡建議:{suggest_qty:.1f})"
                )
                last_item_display_name = display_name

            with c2:
                stock_qty = st.number_input(
                    "庫",
                    min_value=0.0,
                    step=0.1,
                    key=f"s_{item_id}",
                    format="%.1f",
                    value=0.0,
                    label_visibility="collapsed",
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
                    "previous_stock": previous_stock,
                    "previous_order": previous_order,
                    "avg_usage": avg_usage,
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

    st.button(
        "⬅️ 返回功能選單",
        use_container_width=True,
        disabled=True,
        help="之後再接回選單邏輯",
    )


def page_order_history() -> None:
    _page_header("叫貨紀錄", "查看歷史叫貨資料、廠商進貨內容與金額。")
    st.info("骨架版：此頁先保留位置，後續再接 purchase_orders / purchase_order_lines。")


def page_stocktake_history() -> None:
    _page_header("盤點歷史", "查看每次盤點前後的庫存變化與期間消耗。")
    st.info("骨架版：此頁先保留位置，後續再接 stocktakes / stocktake_lines。")
    st.write("上次庫存 + 期間進貨 - 這次庫存 = 期間消耗")
