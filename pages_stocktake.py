import streamlit as st
import pandas as pd


# ---------------------------------------------------------
# 手機版 UI 壓縮樣式
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
def page_stocktake(items_df, units_df):

    apply_compact_style()

    st.title("點貨 / 叫貨")

    results = []

    for _, item in items_df.iterrows():

        row = render_item_row(item, units_df)

        results.append(row)

        st.divider()

    note = st.text_input("備註")

    if st.button("✅ 一次送出"):

        df = pd.DataFrame(results)

        st.write("送出資料")

        st.dataframe(df)

        # 這裡之後會接 DB 寫入
