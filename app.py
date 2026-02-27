import pandas as pd
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

# =========================
# 1. Google Sheets 設定
# =========================
# 請將你的 JSON 憑證檔案放在同資料夾，並改名為 'service_account.json'
JSON_KEY_FILE = 'service_account.json' 
# 請填入你 Google 試算表的 ID
SHEET_ID = '叫貨系統資料庫' 

def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_KEY_FILE, scope)
    return gspread.authorize(creds)

def sync_data_to_gs(df_to_save):
    try:
        client = get_gspread_client()
        sh = client.open_by_key(SHEET_ID)
        try:
            ws = sh.worksheet("Records")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title="Records", rows="1000", cols="20")
            ws.append_row(['record_date', 'store_name', 'vendor_name', 'item_name', 'last_stock', 'last_purchase', 'this_stock', 'this_purchase', 'usage_qty'])
        
        # 轉換為列表並存入
        data_list = df_to_save.values.tolist()
        ws.append_rows(data_list)
        return True
    except Exception as e:
        st.error(f"雲端同步失敗: {e}")
        return False

def get_prev_data_from_gs(store, item, current_date):
    try:
        client = get_gspread_client()
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet("Records")
        all_data = pd.DataFrame(ws.get_all_records())
        if all_data.empty: return 0, 0
        
        all_data['record_date'] = pd.to_datetime(all_data['record_date']).dt.date
        past_data = all_data[(all_data['store_name'] == store) & 
                             (all_data['item_name'] == item) & 
                             (all_data['record_date'] < current_date)]
        
        if not past_data.empty:
            latest = past_data.sort_values(by='record_date', ascending=False).iloc[0]
            return int(latest['this_stock']), int(latest['this_purchase'])
    except:
        pass
    return 0, 0

# =========================
# 2. 原始 CSV 載入 (維持不變)
# =========================
CSV_STORE = Path("品項總覽.xlsx - 分店.csv")
CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv")

def load_csv_safe(path):
    for enc in ['utf-8', 'cp950', 'big5']:
        try:
            df = pd.read_csv(path, encoding=enc)
            return df.map(lambda x: x.strip() if isinstance(x, str) else x)
        except: continue
    return None

st.set_page_config(page_title="雲端進銷存系統", layout="wide")
df_s, df_i = load_csv_safe(CSV_STORE), load_csv_safe(CSV_ITEMS)

if "step" not in st.session_state: st.session_state.step = "select_store"
if "record_date" not in st.session_state: st.session_state.record_date = date.today()

# --- 介面流程 (簡化示意，邏輯同前，但儲存改用 sync_data_to_gs) ---
if st.session_state.step == "select_store":
    st.title("🏠 雲端同步：選擇分店")
    for s in df_s['分店名稱'].unique():
        if st.button(f"📍 {s}", use_container_width=True):
            st.session_state.store = s
            st.session_state.step = "select_vendor"
            st.rerun()

elif st.session_state.step == "select_vendor":
    st.title(f"🏢 {st.session_state.store}")
    st.session_state.record_date = st.date_input("🗓️ 日期", value=st.session_state.record_date)
    vendors = sorted(df_i['廠商名稱'].unique())
    for v in vendors:
        if st.button(f"📦 {v}", use_container_width=True):
            st.session_state.vendor = v
            st.session_state.step = "fill_items"
            st.rerun()
    if st.button("📄 產生叫貨報表"): st.session_state.step = "export"; st.rerun()

elif st.session_state.step == "fill_items":
    st.title(f"📝 {st.session_state.vendor}")
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    
    with st.form("inventory_form"):
        temp_rows = []
        for _, row in items.iterrows():
            name = row['品項名稱']
            prev_s, prev_p = get_prev_data_from_gs(st.session_state.store, name, st.session_state.record_date)
            st.write(f"--- **{name}** (上次結餘: {prev_s + prev_p})")
            c1, c2 = st.columns(2)
            t_s = c1.number_input(f"剩餘", min_value=0, key=f"s_{name}")
            t_p = c2.number_input(f"叫貨", min_value=0, key=f"p_{name}")
            usage = prev_s + prev_p - t_s
            temp_rows.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, name, prev_s, prev_p, int(t_s), int(t_p), int(usage)])
            
        if st.form_submit_button("💾 儲存並同步至雲端"):
            df_to_save = pd.DataFrame(temp_rows, columns=['record_date', 'store_name', 'vendor_name', 'item_name', 'last_stock', 'last_purchase', 'this_stock', 'this_purchase', 'usage_qty'])
            if sync_data_to_gs(df_to_save):
                st.success("✅ 雲端同步成功！")
                st.session_state.step = "select_vendor"
                st.rerun()

# (Export 報表部分可依此類推，從 ws.get_all_records() 抓取資料)
