import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = "1c9twPCyOumPKSau5xgUShJJAG-D9aaZBhK2FWBl2zwc"

@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds_info = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"⚠️ 金鑰連線失敗: {e}")
        return None

def get_worksheet_data(sheet_name: str) -> pd.DataFrame:
    try:
        client = get_gspread_client()
        if not client:
            return pd.DataFrame()
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]

        num_cols = ["上次剩餘", "上次叫貨", "本次剩餘", "本次叫貨", "期間消耗", "單價", "總金額"]
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        return df
    except Exception:
        return pd.DataFrame()

def get_cloud_data() -> pd.DataFrame:
    return get_worksheet_data("Records")

def sync_to_cloud(df_to_save: pd.DataFrame) -> bool:
    client = get_gspread_client()
    if not client:
        return False
    try:
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet("Records")
        ws.append_rows(df_to_save.values.tolist())
        return True
    except Exception:
        return False
