import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date
from pathlib import Path

# =========================
# 1. Google Sheets 核心設定
# =========================
SHEET_ID = '1c9twPCyOumPKSau5xgUShJJAG-D9aaZBhK2FWBl2zwc' 

def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        if "gcp_service_account" in st.secrets:
            creds_info = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"⚠️ 金鑰讀取失敗: {e}")
        return None

def get_prev_data(store, item):
    try:
        client = get_gspread_client()
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet("Records")
        all_data = pd.DataFrame(ws.get_all_records())
        if all_data.empty: return 0, 0
        
        past = all_data[(all_data['store_name'] == store) & (all_data['item_name'] == item)]
        if not past.empty:
            latest = past.iloc[-1]
            return int(latest['this_stock']), int(latest['this_purchase'])
    except:
        pass
    return 0, 0

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
        st.error(f"❌ 寫入失敗: {e}")
        return False

# =========================
# 2. 檔案載入
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

# =========================
# 3. 介面流程
# =========================

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
    st.session_state.record_date = st.date_input("📅 選擇叫貨日期", value=st.session_state.record_date)
    st.write("---")
    vendors = sorted(df_i['廠商名稱'].unique())
    for v in vendors:
        if st.button(f"📦 {v}", use_container_width=True):
            st.session_state.vendor = v
            st.session_state.step = "fill_items"
            st.rerun()
            
    if st.button("⬅️ 返回選擇分店", use_container_width=True):
        st.session_state.step = "select_store"
        st.rerun()

elif st.session_state.step == "fill_items":
    st.title(f"📝 {st.session_state.vendor}")
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    
    with st.form("inventory_form"):
        temp_rows = []
        for _, row in items.iterrows():
            name = row['品項名稱']
            
            # 抓取上次紀錄
            prev_s, prev_p = get_prev_data(st.session_state.store, name)
            st.write(f"**【{name}】** (上次結餘: {prev_s + prev_p})")
            
            c1, c2 = st.columns(2)
            ts = c1.number_input(f"本次剩餘", min_value=0, step=1, key=f"s_{name}")
            tp = c2.number_input(f"本次叫貨", min_value=0, step=1, key=f"p_{name}")
            
            # 計算使用量 (期間使用量 = 上次剩餘 + 上次叫貨 - 本次剩餘)
            usage = (prev_s + prev_p) - ts
            
            # 💡 戰略過濾：只有當「叫貨量 > 0」或「剩餘量 > 0」時才加入待上傳清單
            if ts > 0 or tp > 0:
                temp_rows.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, name, int(prev_s), int(prev_p), int(ts), int(tp), int(usage)])
        
        col1, col2 = st.columns(2)
        if col1.form_submit_button("💾 儲存並同步雲端"):
            if not temp_rows:
                st.warning("⚠️ 沒有填寫任何數量，取消同步。")
            else:
                cols = ['record_date', 'store_name', 'vendor_name', 'item_name', 'last_stock', 'last_purchase', 'this_stock', 'this_purchase', 'usage_qty']
                df_to_save = pd.DataFrame(temp_rows, columns=cols)
                if sync_data_to_gs(df_to_save):
                    st.success(f"✅ 同步成功！已寫入 {len(temp_rows)} 筆資料。")
                    st.session_state.step = "select_store"
                    st.rerun()
        if col2.form_submit_button("❌ 不叫貨（返回）"):
            st.session_state.step = "select_vendor"
            st.rerun()
