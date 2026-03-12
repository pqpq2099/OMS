"""
OMS 核心模組
統一負責 Google Sheet 讀寫
"""

from __future__ import annotations

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials


DEFAULT_SHEET_ID = "1L1ogNjLWjjH8usMWC2JQowMMZkfD4zkuE-4UcgiTqXQ"


# ============================================================
# Google Sheet 連線
# ============================================================

@st.cache_resource
def get_client():
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
    else:
        creds = Credentials.from_service_account_file(
            "service_account.json",
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )

    return gspread.authorize(creds)


@st.cache_resource
def get_spreadsheet():
    client = get_client()
    return client.open_by_key(DEFAULT_SHEET_ID)


def get_worksheet(name: str):
    sh = get_spreadsheet()
    return sh.worksheet(name)


# ============================================================
# 讀取資料
# ============================================================

def read_table(name: str) -> pd.DataFrame:
    ws = get_worksheet(name)
    data = ws.get_all_records()

    if not data:
        return pd.DataFrame()

    return pd.DataFrame(data)


# ============================================================
# 覆蓋整張表
# ============================================================

def overwrite_table(name: str, df: pd.DataFrame):

    ws = get_worksheet(name)

    ws.clear()

    if df is None or df.empty:
        ws.update([[]])
        return

    ws.update(
        [df.columns.tolist()]
        + df.astype(str).values.tolist()
    )


# ============================================================
# 新增列
# ============================================================

def append_rows_by_header(name: str, rows: list[dict]):

    if not rows:
        return

    ws = get_worksheet(name)

    header = ws.row_values(1)

    out = []

    for r in rows:
        row = []
        for h in header:
            row.append(r.get(h, ""))

        out.append(row)

    ws.append_rows(out)


# ============================================================
# 清除 cache
# ============================================================

def bust_cache():
    st.cache_data.clear()
    st.cache_resource.clear()
# ============================================================
# 全域樣式
# ============================================================
def apply_global_style():
    """
    Streamlit 全域 UI 樣式
    """
    import streamlit as st

    st.markdown(
        """
        <style>

        .block-container{
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }

        h1, h2, h3 {
            font-weight: 600;
        }

        .stButton>button {
            border-radius: 8px;
        }

        </style>
        """,
        unsafe_allow_html=True
    )
