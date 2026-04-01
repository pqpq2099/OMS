# ============================================================
# ORIVIA OMS
# 檔案：pages/page_stocktake.py
# 說明：盤點頁
# 功能：執行盤點相關輸入、檢視與提交流程。
# 注意：若盤點流程異常，優先檢查此頁與 service_stocktake。
# ============================================================

"""
頁面模組：盤點頁。
這個檔案主要是手機版盤點 UI 範例與盤點輸入頁。
如果之後要調整盤點欄位大小、排版、手機畫面，優先看這個檔案。
"""

import streamlit as st

from shared.core.navigation import goto
from operations.logic.logic_stocktake import build_stocktake_page_tables, build_stocktake_submit_df



# ---------------------------------------------------------
# [S1] 手機版 UI 壓縮樣式
# 你如果覺得欄位太寬、按鈕太高、數字框跑版，
# 先來改這裡的 CSS。
# ---------------------------------------------------------
def apply_compact_style():
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1rem;
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }

        div[data-testid="stNumberInputStepUp"],
        div[data-testid="stNumberInputStepDown"] {
            display: none;
        }

        input[type=number] {
            -moz-appearance: textfield;
        }

        [data-testid="stHorizontalBlock"] {
            gap: 0.4rem;
            flex-wrap: nowrap !important;
            align-items: center !important;
        }

        [data-testid="column"] {
            min-width: 0 !important;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# 單列 UI
# ---------------------------------------------------------

# ---------------------------------------------------------
# [S2] 單一品項列 UI
# 這裡控制每一列盤點品項怎麼顯示。
# 例如：品名、庫存欄、單位欄、提示文字。
# ---------------------------------------------------------
def render_item_row(item, units_df):

    item_id = item["item_id"]
    name = item["name"]

    stock_unit = item["stock_unit_name"]
    order_unit = item["order_unit_name"]

    price = item.get("price_today", 0)
    prev = item.get("prev_order", 0)
    suggest = item.get("suggest", 0)

    col_name, col_stock, col_stock_unit, col_order, col_order_unit = st.columns(
        [5, 2, 2, 2, 2]
    )

    with col_name:

        st.markdown(f"**{name}**")

        st.caption(
            f"單價:{price}｜上次:{prev}｜建議:{suggest}"
        )

    with col_stock:

        stock_qty = st.number_input(
            "庫",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key=f"stk_qty_{item_id}",
            label_visibility="collapsed",
        )

    with col_stock_unit:

        stock_unit_id = st.selectbox(
            "庫單位",
            units_df["name"],
            index=units_df.index[units_df["name"] == stock_unit][0],
            key=f"stk_unit_{item_id}",
            label_visibility="collapsed",
        )

    with col_order:

        order_qty = st.number_input(
            "進",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key=f"ord_qty_{item_id}",
            label_visibility="collapsed",
        )

    with col_order_unit:

        order_unit_id = st.selectbox(
            "進單位",
            units_df["name"],
            index=units_df.index[units_df["name"] == order_unit][0],
            key=f"ord_unit_{item_id}",
            label_visibility="collapsed",
        )

    return {
        "item_id": item_id,
        "stock_qty": stock_qty,
        "stock_unit": stock_unit_id,
        "order_qty": order_qty,
        "order_unit": order_unit_id,
    }


# ---------------------------------------------------------
# 主頁
# ---------------------------------------------------------

# ---------------------------------------------------------
# [S3] 盤點主畫面內容
# ---------------------------------------------------------
def render_page_stocktake(items_df, units_df):

    apply_compact_style()

    st.title("點貨 / 叫貨")

    results = []

    for _, item in items_df.iterrows():

        row = render_item_row(item, units_df)

        results.append(row)

        st.divider()

    note = st.text_input("備註")

    if st.button("✅ 一次送出"):

        df = build_stocktake_submit_df(results)

        st.write("送出資料")

        st.dataframe(df)

        # 這裡之後會接 DB 寫入
# ---------------------------------------------------------
# 頁面入口（給 app.py 用）
# ---------------------------------------------------------

# ---------------------------------------------------------
# [S4] page_stocktake 對外入口
# app.py 會呼叫這個函式進到盤點頁。
# ---------------------------------------------------------
def page_stocktake():

    # 之後改成正式資料來源
    items_df, units_df = build_stocktake_page_tables()

    if items_df.empty:
        st.title("點貨 / 叫貨")
        st.info("⚠️ 此功能尚未開放，請由主選單進行叫貨作業。")
        if st.button("⬅️ 返回", use_container_width=True):
            goto("select_vendor")
        return

    render_page_stocktake(items_df, units_df)
