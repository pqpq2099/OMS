# ============================================================
# ORIVIA OMS - Store Pages
# ============================================================

from __future__ import annotations

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
        options = [u.strip() for u in orderable_units_raw.split(",") if u.strip()]

    if default_order_unit and default_order_unit not in options:
        options.insert(0, default_order_unit)

    if not options:
        fallback = default_order_unit or base_unit or ""
        options = [fallback]

    return options


def page_order_entry() -> None:
    _page_header(
        "叫貨 / 庫存",
        "門市日常操作入口：同頁輸入庫存與進貨。",
    )

    st.info("V2：先完成『選廠商 → 顯示品項 → 輸入庫存 / 進貨 / 單位 → 提交預覽』")

    # --------------------------------------------------------
    # 讀取資料
    # --------------------------------------------------------
    try:
        items = read_table("items")
        vendors = read_table("vendors")
    except Exception as e:
        st.error(f"讀取資料失敗：{e}")
        return

    if items is None or items.empty:
        st.warning("目前沒有 items 資料。")
        st.caption("請先確認 oms_data.py 的 read_table('items') 是否已接到 Google Sheets。")
        return

    if vendors is None or vendors.empty:
        st.warning("目前沒有 vendors 資料。")
        st.caption("請先確認 oms_data.py 的 read_table('vendors') 是否已接到 Google Sheets。")
        return

    items = items.copy()
    vendors = vendors.copy()

    # --------------------------------------------------------
    # 基本欄位檢查
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # 可選欄位補齊
    # --------------------------------------------------------
    items["item_name"] = _safe_col(items, "item_name", "")
    items["item_name_zh"] = _safe_col(items, "item_name_zh", "")
    items["item_type"] = _safe_col(items, "item_type", "")
    items["base_unit"] = _safe_col(items, "base_unit", "")
    items["default_order_unit"] = _safe_col(items, "default_order_unit", "")
    items["default_stock_unit"] = _safe_col(items, "default_stock_unit", "")
    items["orderable_units"] = _safe_col(items, "orderable_units", "")

    # --------------------------------------------------------
    # 廠商選擇
    # --------------------------------------------------------
    vendor_options = vendors[["vendor_id", "vendor_name"]].copy()
    vendor_options["vendor_id"] = vendor_options["vendor_id"].astype(str).str.strip()
    vendor_options["vendor_name"] = vendor_options["vendor_name"].astype(str).str.strip()
    vendor_options = vendor_options[vendor_options["vendor_name"] != ""]

    if vendor_options.empty:
        st.warning("vendors 有資料，但沒有可用的 vendor_name。")
        return

    vendor_name_list = vendor_options["vendor_name"].tolist()

    selected_vendor_name = st.selectbox(
        "選擇廠商",
        options=vendor_name_list,
        index=0,
    )

    selected_vendor_row = vendor_options[vendor_options["vendor_name"] == selected_vendor_name].iloc[0]
    selected_vendor_id = str(selected_vendor_row["vendor_id"]).strip()

    # --------------------------------------------------------
    # 過濾該廠商品項
    # --------------------------------------------------------
    items["default_vendor_id"] = items["default_vendor_id"].astype(str).str.strip()
    vendor_items = items[items["default_vendor_id"] == selected_vendor_id].copy()

    if vendor_items.empty:
        st.warning("此廠商目前沒有綁定品項。")
        return

    # 中文優先，其次 item_name，再其次 item_id
    vendor_items["display_name"] = vendor_items["item_name_zh"].astype(str).str.strip()
    vendor_items.loc[vendor_items["display_name"] == "", "display_name"] = (
        vendor_items["item_name"].astype(str).str.strip()
    )
    vendor_items.loc[vendor_items["display_name"] == "", "display_name"] = (
        vendor_items["item_id"].astype(str).str.strip()
    )

    vendor_items["base_unit"] = vendor_items["base_unit"].astype(str).str.strip()
    vendor_items["default_order_unit"] = vendor_items["default_order_unit"].astype(str).str.strip()
    vendor_items["default_stock_unit"] = vendor_items["default_stock_unit"].astype(str).str.strip()
    vendor_items["orderable_units"] = vendor_items["orderable_units"].astype(str).str.strip()

    st.subheader("品項列表")
    st.caption(f"共 {len(vendor_items)} 項")

    with st.form("order_entry_form"):
        submit_rows = []

        header_cols = st.columns([6, 1.4, 1.4])
        with header_cols[0]:
            st.markdown("**品項名稱**")
        with header_cols[1]:
            st.markdown("**庫**")
        with header_cols[2]:
            st.markdown("**進**")

        st.markdown("---")

        for _, row in vendor_items.iterrows():
            item_id = str(row["item_id"]).strip()
            item_name = str(row["display_name"]).strip()
            base_unit = str(row["base_unit"]).strip()
            default_order_unit = str(row["default_order_unit"]).strip()
            default_stock_unit = str(row["default_stock_unit"]).strip()
            orderable_units_raw = str(row["orderable_units"]).strip()

            order_unit_options = _parse_unit_options(
                orderable_units_raw=orderable_units_raw,
                default_order_unit=default_order_unit,
                base_unit=base_unit,
            )

            block_cols = st.columns([6, 1.4, 1.4])

            with block_cols[0]:
                st.markdown(f"**{item_name}**")
                st.caption(
                    f"庫存單位：{default_stock_unit or base_unit or '-'}　基準單位：{base_unit or '-'}"
                )

            with block_cols[1]:
                stock_qty = st.number_input(
                    f"{item_id}_stock",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                    format="%.1f",
                    label_visibility="collapsed",
                    key=f"stock_{item_id}",
                )
                st.caption(default_stock_unit or base_unit or "-")

            with block_cols[2]:
                order_qty = st.number_input(
                    f"{item_id}_order",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                    format="%.1f",
                    label_visibility="collapsed",
                    key=f"order_{item_id}",
                )

                default_index = 0
                if default_order_unit in order_unit_options:
                    default_index = order_unit_options.index(default_order_unit)

                order_unit = st.selectbox(
                    f"{item_id}_unit",
                    options=order_unit_options,
                    index=default_index,
                    label_visibility="collapsed",
                    key=f"unit_{item_id}",
                )
                st.caption(base_unit or "-")

            submit_rows.append(
                {
                    "vendor_id": selected_vendor_id,
                    "vendor_name": selected_vendor_name,
                    "item_id": item_id,
                    "item_name": item_name,
                    "stock_qty": _safe_float(stock_qty),
                    "order_qty": _safe_float(order_qty),
                    "order_unit": order_unit,
                    "base_unit": base_unit,
                    "stock_unit": default_stock_unit or base_unit,
                }
            )

            st.markdown("")

        st.markdown("---")
        submitted = st.form_submit_button("提交叫貨 / 庫存")

    # --------------------------------------------------------
    # 提交後先做預覽
    # --------------------------------------------------------
    if submitted:
        result_df = pd.DataFrame(submit_rows)

        result_df = result_df[
            (result_df["stock_qty"] > 0) | (result_df["order_qty"] > 0)
        ].copy()

        if result_df.empty:
            st.warning("你還沒有輸入任何庫存或進貨數量。")
            return

        st.success("已完成提交預覽。這一版先不寫入資料庫，只先確認輸入流程正確。")

        preview_df = result_df.rename(
            columns={
                "vendor_name": "廠商",
                "item_id": "品項ID",
                "item_name": "品項名稱",
                "stock_qty": "庫存",
                "order_qty": "進貨",
                "order_unit": "進貨單位",
                "base_unit": "基準單位",
                "stock_unit": "庫存單位",
            }
        )[
            ["廠商", "品項ID", "品項名稱", "庫存", "庫存單位", "進貨", "進貨單位", "基準單位"]
        ]

        st.subheader("提交預覽")
        st.dataframe(preview_df, use_container_width=True, hide_index=True)

        st.caption("下一步會接 purchase_orders / purchase_order_lines 寫入。")


def page_order_history() -> None:
    _page_header("叫貨紀錄", "查看歷史叫貨資料、廠商進貨內容與金額。")

    st.info("骨架版：此頁先保留位置，後續再接 purchase_orders / purchase_order_lines。")

    st.subheader("預計內容")
    st.write("之後會放：日期篩選、分店篩選、廠商篩選、進貨明細表。")


def page_stocktake_history() -> None:
    _page_header("盤點歷史", "查看每次盤點前後的庫存變化與期間消耗。")

    st.info("骨架版：此頁先保留位置，後續再接 stocktakes / stocktake_lines。")

    st.subheader("固定邏輯")
    st.write("上次庫存 + 期間進貨 - 這次庫存 = 期間消耗")

    st.subheader("預計欄位")
    st.write("日期 / 品項 / 上次庫存 / 期間進貨 / 庫存合計 / 這次庫存 / 期間消耗 / 日平均")
