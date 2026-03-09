# ============================================================
# ORIVIA OMS - app.py
# 最小可跑骨架版
# 只保留：
# 1. Streamlit 基本設定
# 2. Sidebar
# 3. Router
# 4. Main
# ============================================================

from __future__ import annotations

import streamlit as st

from oms_pages_store import (
    page_order_entry,
    page_order_history,
    page_stocktake_history,
)
from oms_pages_analysis import (
    page_inventory_analysis,
    page_cost_analysis,
    page_purchase_report,
)
from oms_pages_admin import (
    page_vendors,
    page_items,
    page_stores,
    page_brands,
    page_users,
)
from oms_pages_settings import (
    page_appearance,
    page_operation_rules,
    page_inventory_rules,
)
from oms_pages_system import page_system_info


APP_TITLE = "ORIVIA OMS"
APP_ICON = "📦"

MENU_TREE: dict[str, list[str]] = {
    "門市營運": [
        "叫貨 / 庫存",
        "叫貨紀錄",
        "盤點歷史",
    ],
    "數據分析": [
        "進銷存分析",
        "成本分析",
        "進貨報表",
    ],
    "系統管理": [
        "廠商管理",
        "品項管理",
        "分店管理",
        "品牌管理",
        "帳號權限",
    ],
    "系統設定": [
        "外觀設定",
        "營運規則",
        "庫存規則",
    ],
    "系統資訊": [
        "系統資訊",
    ],
}


def build_sidebar() -> tuple[str, str]:
    """建立左側主選單與子選單。"""
    with st.sidebar:
        st.title(APP_TITLE)
        st.caption("系統骨架版")

        menu_main = st.selectbox(
            "功能分類",
            options=list(MENU_TREE.keys()),
            index=0,
        )

        menu_sub = st.radio(
            "選擇功能",
            options=MENU_TREE[menu_main],
            index=0,
        )

    return menu_main, menu_sub


def route_page(menu_sub: str) -> None:
    """依子選單導向對應頁面。"""
    # 門市營運
    if menu_sub == "叫貨 / 庫存":
        page_order_entry()
    elif menu_sub == "叫貨紀錄":
        page_order_history()
    elif menu_sub == "盤點歷史":
        page_stocktake_history()

    # 數據分析
    elif menu_sub == "進銷存分析":
        page_inventory_analysis()
    elif menu_sub == "成本分析":
        page_cost_analysis()
    elif menu_sub == "進貨報表":
        page_purchase_report()

    # 系統管理
    elif menu_sub == "廠商管理":
        page_vendors()
    elif menu_sub == "品項管理":
        page_items()
    elif menu_sub == "分店管理":
        page_stores()
    elif menu_sub == "品牌管理":
        page_brands()
    elif menu_sub == "帳號權限":
        page_users()

    # 系統設定
    elif menu_sub == "外觀設定":
        page_appearance()
    elif menu_sub == "營運規則":
        page_operation_rules()
    elif menu_sub == "庫存規則":
        page_inventory_rules()

    # 系統資訊
    elif menu_sub == "系統資訊":
        page_system_info()

    else:
        st.warning("找不到對應頁面。")


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        layout="wide",
    )

    _, menu_sub = build_sidebar()
    route_page(menu_sub)


if __name__ == "__main__":
    main()# [B3] Sheet Read
# ============================================================

@st.cache_data(ttl=30)
def read_sheet(sheet_name):

    gc = get_gsheet_client()

    sh = gc.open_by_key(DEFAULT_SHEET_ID)

    ws = sh.worksheet(sheet_name)

    data = ws.get_all_records()

    return pd.DataFrame(data)


# ============================================================
# [B4] Sheet Write
# ============================================================

def append_rows(sheet_name, rows):

    gc = get_gsheet_client()

    sh = gc.open_by_key(DEFAULT_SHEET_ID)

    ws = sh.worksheet(sheet_name)

    ws.append_rows(rows, value_input_option="USER_ENTERED")


# ============================================================
# [B5] ID Sequence
# ============================================================

def allocate_ids(key, count=1):

    seq_df = read_sheet("id_sequences")

    row = seq_df[seq_df["key"] == key]

    if row.empty:
        raise Exception("sequence not found")

    current = int(row.iloc[0]["current_value"])

    new_ids = []

    for i in range(count):

        new_ids.append(current + i + 1)

    return new_ids


# ============================================================
# [C1] Data Helpers
# ============================================================

def get_items():

    df = read_sheet("items")

    return df[df["is_active"] == True]


def get_vendors():

    df = read_sheet("vendors")

    return df[df["is_active"] == True]


# ============================================================
# [D1] Session State
# ============================================================

if "page" not in st.session_state:
    st.session_state.page = "store_select"


# ============================================================
# [D2] Sidebar
# ============================================================

def render_sidebar():

    with st.sidebar:

        st.title("ORIVIA OMS")

        if st.button("叫貨 / 庫存"):
            st.session_state.page = "order"

        if st.button("歷史紀錄"):
            st.session_state.page = "history"

        if st.button("進銷存分析"):
            st.session_state.page = "analysis"

        if st.button("成本檢查"):
            st.session_state.page = "cost"


# ============================================================
# [E1] Order Page
# ============================================================

def page_order():

    st.title("叫貨 / 庫存")

    vendors = get_vendors()

    vendor = st.selectbox(
        "選擇廠商",
        vendors["vendor_name"]
    )

    items = get_items()

    st.write(items)


# ============================================================
# [E2] History
# ============================================================

def page_history():

    st.title("歷史庫存")

    df = read_sheet("stocktakes")

    st.dataframe(df)


# ============================================================
# [E3] Analysis
# ============================================================

def page_analysis():

    st.title("進銷存分析")

    if not HAS_PLOTLY:
        st.warning("plotly 未安裝")
        return

    df = read_sheet("purchase_order_lines")

    if df.empty:
        st.info("無資料")
        return

    fig = px.line(df, x="date", y="qty")

    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# [E4] Cost Debug
# ============================================================

def page_cost_debug():

    st.title("成本檢查")

    items = get_items()

    item = st.selectbox(
        "選擇品項",
        items["item_name"]
    )

    st.write("成本計算測試")


# ============================================================
# [F1] Router
# ============================================================

def router():

    page = st.session_state.page

    if page == "order":
        page_order()

    elif page == "history":
        page_history()

    elif page == "analysis":
        page_analysis()

    elif page == "cost":
        page_cost_debug()


# ============================================================
# [G1] Main
# ============================================================

def main():

    render_sidebar()

    router()


if __name__ == "__main__":
    main()        page_inventory_analysis()
    elif menu_sub == "成本分析":
        page_cost_analysis()
    elif menu_sub == "進貨報表":
        page_purchase_report()

    # 系統管理
    elif menu_sub == "廠商管理":
        page_vendors()
    elif menu_sub == "品項管理":
        page_items()
    elif menu_sub == "分店管理":
        page_stores()
    elif menu_sub == "品牌管理":
        page_brands()
    elif menu_sub == "帳號權限":
        page_users()

    # 系統設定
    elif menu_sub == "外觀設定":
        page_appearance()
    elif menu_sub == "營運規則":
        page_operation_rules()
    elif menu_sub == "庫存規則":
        page_inventory_rules()

    # 系統資訊
    elif menu_sub == "系統資訊":
        page_system_info()

    else:
        st.warning("找不到對應頁面。")


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        layout="wide",
    )

    _, menu_sub = build_sidebar()
    route_page(menu_sub)


if __name__ == "__main__":
    main()


