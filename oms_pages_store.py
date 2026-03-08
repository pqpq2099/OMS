# ============================================================
# ORIVIA OMS - Store Pages
# ============================================================

from __future__ import annotations

import streamlit as st
import pandas as pd

from oms_data import read_table


def _page_header(title: str, desc: str) -> None:
    st.title(title)
    st.caption(desc)
    st.divider()


def _safe_col(df: pd.DataFrame, col_name: str, default_value="") -> pd.Series:
    if col_name in df.columns:
        return df[col_name]
    return pd.Series([default_value] * len(df), index=df.index)


def page_order_entry() -> None:
    _page_header(
        "叫貨 / 庫存",
        "門市日常操作入口：先完成『選廠商 → 顯示品項』。",
    )

    st.info("V1：先確認 items / vendors 能正常讀取，並依廠商顯示品項。")

    # --------------------------------------------------------
    # 讀取資料
    # --------------------------------------------------------
    try:
        items = read_table("items")
        vendors = read_table("vendors")
    except Exception as e:
        st.error(f"讀取資料失敗：{e}")
        return

    # --------------------------------------------------------
    # 基本檢查
    # --------------------------------------------------------
    if items is None or items.empty:
        st.warning("目前沒有 items 資料。")
        st.caption("請先確認 oms_data.py 的 read_table('items') 是否已接到 Google Sheets。")
        return

    if vendors is None or vendors.empty:
        st.warning("目前沒有 vendors 資料。")
        st.caption("請先確認 oms_data.py 的 read_table('vendors') 是否已接到 Google Sheets。")
        return

    # --------------------------------------------------------
    # 欄位補齊，避免缺欄位直接炸掉
    # --------------------------------------------------------
    items = items.copy()
    vendors = vendors.copy()

    if "vendor_id" not in vendors.columns:
        st.error("vendors 缺少欄位：vendor_id")
        return

    if "vendor_name" not in vendors.columns:
        st.error("vendors 缺少欄位：vendor_name")
        return

    if "default_vendor_id" not in items.columns:
        st.error("items 缺少欄位：default_vendor_id")
        return

    if "item_id" not in items.columns:
        st.error("items 缺少欄位：item_id")
        return

    # 這些欄位若沒有就補空值
    items["item_name"] = _safe_col(items, "item_name", "")
    items["item_name_zh"] = _safe_col(items, "item_name_zh", "")
    items["default_order_unit"] = _safe_col(items, "default_order_unit", "")
    items["base_unit"] = _safe_col(items, "base_unit", "")
    items["item_type"] = _safe_col(items, "item_type", "")

    # --------------------------------------------------------
    # 可選廠商
    # --------------------------------------------------------
    vendor_options = vendors[["vendor_id", "vendor_name"]].copy()
    vendor_options["vendor_name"] = vendor_options["vendor_name"].astype(str).fillna("").str.strip()
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
    items["default_vendor_id"] = items["default_vendor_id"].astype(str).fillna("").str.strip()
    vendor_items = items[items["default_vendor_id"] == selected_vendor_id].copy()

    st.subheader("品項列表")

    if vendor_items.empty:
        st.warning("此廠商目前沒有綁定品項。")
        return

    # 中文優先，其次 item_name，再其次 item_id
    vendor_items["顯示品名"] = vendor_items["item_name_zh"].astype(str).str.strip()
    vendor_items.loc[vendor_items["顯示品名"] == "", "顯示品名"] = (
        vendor_items["item_name"].astype(str).str.strip()
    )
    vendor_items.loc[vendor_items["顯示品名"] == "", "顯示品名"] = (
        vendor_items["item_id"].astype(str).str.strip()
    )

    display_df = pd.DataFrame({
        "品項ID": vendor_items["item_id"].astype(str).str.strip(),
        "品項名稱": vendor_items["顯示品名"],
        "品項類型": vendor_items["item_type"].astype(str).str.strip(),
        "叫貨單位": vendor_items["default_order_unit"].astype(str).str.strip(),
        "基準單位": vendor_items["base_unit"].astype(str).str.strip(),
    })

    st.caption(f"共 {len(display_df)} 項")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # --------------------------------------------------------
    # 頁面說明
    # --------------------------------------------------------
    st.divider()
    st.subheader("下一步預計加入")
    st.write("庫存欄位、進貨欄位、叫貨單位下拉、提交按鈕、寫入 purchase_orders / purchase_order_lines。")


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
