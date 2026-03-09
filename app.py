# ============================================================
# ORIVIA OMS 1.0 外觀 + OMS 2.0 資料庫（穩定整合版）
# sidebar + 成本檢查頁
# ============================================================

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

from oms_engine import convert_to_base, convert_unit, get_base_unit

# Plotly
try:
    import plotly.express as px
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False


# ============================================================
# [A1] Config
# ============================================================

DEFAULT_SHEET_ID = "1L1ogNjLWjjH8usMWC2JQowMMZkfD4zkuE-4UcgiTqXQ"

LOCAL_SERVICE_ACCOUNT = Path("service_account.json")

PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "scrollZoom": False,
    "doubleClick": False,
}


# ============================================================
# [A2] UI Style
# ============================================================

st.set_page_config(
    page_title="ORIVIA OMS",
    page_icon="📦",
    layout="wide"
)


# ============================================================
# [B1] Helpers
# ============================================================

def _norm(v):
    if v is None:
        return ""
    return str(v).strip()


def _safe_float(v):
    try:
        return float(v)
    except:
        return 0.0


def _now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# [B2] Google Sheet Client
# ============================================================

@st.cache_resource
def get_gsheet_client():

    if "gcp" in st.secrets:

        creds = Credentials.from_service_account_info(
            st.secrets["gcp"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )

    else:

        creds = Credentials.from_service_account_file(
            LOCAL_SERVICE_ACCOUNT,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )

    return gspread.authorize(creds)


# ============================================================
# [B3] Sheet Read
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

