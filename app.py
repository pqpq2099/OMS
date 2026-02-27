import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date
from pathlib import Path

# =========================
# 1. Google Sheets 核心設定
# =========================
# 💡 請務必確認這裡的 ID 是正確的（網址中 d/ 後面那串）
SHEET_ID = '1X58XpXp_你的試算表ID_請替換此處' 

def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # 直接從你剛填好的 Secrets 抓取資料
    try:
        creds_info = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"金鑰讀取失敗，請檢查 Secrets 設定: {e}")
        return None

def sync_data_to_gs(df_to_save):
    client = get_gspread_client()
    if not client: return False
    try:
        sh = client.open_by_key(SHEET_ID)
        try:
            ws = sh.worksheet("Records")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title="Records", rows="1000", cols="20")
            ws.append_row(['record_date', 'store_name', 'vendor_name', 'item_name', 'last_stock', 'last_purchase', 'this_stock', 'this_purchase', 'usage_qty'])
        
        ws.append_rows(df_to_save.values.tolist())
        return True
    except Exception as e:
        st.error(f"寫入 Google 表格失敗: {e}")
        return False

# =========================
# 2. 檔案載入與介面
# =========================
CSV_STORE = Path("品項總覽.xlsx - 分店.csv")
CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv")

def load_csv_safe(path):
    for enc in ['utf-8', 'cp950', 'big5']:
        try:
            return pd.read_csv(path, encoding=enc)
        except: continue
    return None

st.set_page_config(page_title="雲端進銷存", layout="wide")
df_s, df_i = load_csv_safe(CSV_STORE), load_csv_safe(CSV_ITEMS)

if "step" not in st.session_state: st.session_state.step = "select_store"

# --- 流程控制 ---
if st.session_state.step == "select_store":
    st.title("🏠 選擇分店")
    if df_s is not None:
        for s in df_s['分店名稱'].unique():
            if st.button(f"📍 {s}", use_container_width=True):
                st.session_state.store = s
                st.session_state.step = "select_vendor"
                st.rerun()

elif st.session_state.step == "select_vendor":
    st.title(f"🏢 {st.session_state.store}")
    vendors = sorted(df_i['廠商名稱'].unique())
    for v in vendors:
        if st.button(f"📦 {v}", use_container_width=True):
            st.session_state.vendor = v
            st.session_state.step = "fill_items"
            st.rerun()

elif st.session_state.step == "fill_items":
    st.title(f"📝 {st.session_state.vendor}")
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    with st.form("my_form"):
        temp_rows = []
        for _, row in items.iterrows():
            name = row['品項名稱']
            st.write(f"**{name}**")
            c1, c2 = st.columns(2)
            ts = c1.number_input("剩餘量", min_value=0, key=f"s_{name}")
            tp = c2.number_input("叫貨量", min_value=0, key=f"p_{name}")
            temp_rows.append([str(date.today()), st.session_state.store, st.session_state.vendor, name, 0, 0, ts, tp, 0])
        
        if st.form_submit_button("💾 儲存並同步"):
            df_to_save = pd.DataFrame(temp_rows)
            if sync_data_to_gs(df_to_save):
                st.success("同步成功！")
                st.session_state.step = "select_store"
                st.rerun()
