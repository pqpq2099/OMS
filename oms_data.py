# ============================================================
# ORIVIA OMS - Data Layer
# ============================================================

from __future__ import annotations

import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


# ------------------------------------------------------------
# Google Sheets 連線
# ------------------------------------------------------------
@st.cache_resource
def _get_gspread_client():

    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope,
    )

    return gspread.authorize(creds)


@st.cache_resource
def _get_spreadsheet():

    client = _get_gspread_client()

    SHEET_ID = st.secrets["SHEET_ID"]

    return client.open_by_key(SHEET_ID)


# ------------------------------------------------------------
# 讀取資料表
# ------------------------------------------------------------
@st.cache_data(ttl=60)
def read_table(table_name: str) -> pd.DataFrame:

    try:
        sheet = _get_spreadsheet()

        worksheet = sheet.worksheet(table_name)

        records = worksheet.get_all_records()

        df = pd.DataFrame(records)

        return df

    except Exception as e:

        st.warning(f"讀取資料表 {table_name} 失敗：{e}")

        return pd.DataFrame()
