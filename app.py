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

@st.cache_resource
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

def get_all_historical_data():
    try:
        client = get_gspread_client()
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet("Records")
        return pd.DataFrame(ws.get_all_records())
    except:
        return pd.DataFrame()

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
                # 進到廠商頁面前，先抓一次歷史紀錄
                st.session_state.history_df = get_all_historical_data()
                st.session_state.step = "select_vendor"
                st.rerun()

elif st.session_state.step == "select_vendor":
    st.title(f"🏢 {st.session_state.store} - 管理看板")
    
    # --- 💡 新增：歷史明細與統計區塊 ---
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    tab1, tab2 = st.tabs(["📦 開始叫貨", "📊 歷史明細與統計"])
    
    with tab1:
        st.session_state.record_date = st.date_input("📅 選擇叫貨日期", value=st.session_state.record_date)
        st.write("### 選擇廠商填寫單據")
        vendors = sorted(df_i['廠商名稱'].unique())
        for v in vendors:
            if st.button(f"🚀 進入 {v}", use_container_width=True):
                st.session_state.vendor = v
                st.session_state.step = "fill_items"
                st.rerun()
        
        st.write("---")
        if st.button("⬅️ 返回選擇分店", use_container_width=True):
            st.session_state.step = "select_store"
            st.rerun()

    with tab2:
        if not hist_df.empty:
            # 僅篩選目前分店的資料
            store_hist = hist_df[hist_df['store_name'] == st.session_state.store].copy()
            
            if not store_hist.empty:
                st.subheader("📋 近期叫貨明細")
                st.dataframe(store_hist.sort_values('record_date', ascending=False), use_container_width=True)
                
                st.write("---")
                st.subheader("📈 品項期間匯總 (產生明細)")
                # 💡 戰略核心：自動加總該店所有紀錄
                summary = store_hist.groupby('item_name').agg({
                    'this_purchase': 'sum',
                    'usage_qty': 'sum'
                }).rename(columns={'this_purchase': '累計叫貨', 'usage_qty': '累計使用量'})
                st.table(summary)
            else:
                st.info("目前尚無該分店的歷史紀錄。")
        else:
            st.warning("無法抓取雲端歷史資料，請確認 Google Sheets 權限。")

elif st.session_state.step == "fill_items":
    st.title(f"📝 {st.session_state.vendor}")
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    with st.form("inventory_form"):
        temp_rows = []
        for _, row in items.iterrows():
            name = row['品項名稱']
            
            # 從緩存中找該店、該品項的最後一次紀錄
            prev_s, prev_p = 0, 0
            if not hist_df.empty:
                past = hist_df[(hist_df['store_name'] == st.session_state.store) & (hist_df['item_name'] == name)]
                if not past.empty:
                    latest = past.iloc[-1]
                    prev_s, prev_p = int(latest['this_stock']), int(latest['this_purchase'])

            st.write(f"**【{name}】** (上次結餘: {prev_s + prev_p})")
            c1, c2 = st.columns(2)
            ts = c1.number_input(f"本次剩餘", min_value=0, step=1, key=f"s_{name}")
            tp = c2.number_input(f"本次叫貨", min_value=0, step=1, key=f"p_{name}")
            
            usage = (prev_s + prev_p) - ts
            if ts > 0 or tp > 0:
                temp_rows.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, name, int(prev_s), int(prev_p), int(ts), int(tp), int(usage)])
        
        col1, col2 = st.columns(2)
        if col1.form_submit_button("💾 儲存並同步雲端"):
            if not temp_rows:
                st.warning("⚠️ 內容皆為 0，未進行同步。")
            else:
                cols = ['record_date', 'store_name', 'vendor_name', 'item_name', 'last_stock', 'last_purchase', 'this_stock', 'this_purchase', 'usage_qty']
                df_to_save = pd.DataFrame(temp_rows, columns=cols)
                if sync_data_to_gs(df_to_save):
                    st.success("✅ 同步成功！")
                    st.session_state.step = "select_store"
                    st.rerun()
        if col2.form_submit_button("❌ 返回"):
            st.session_state.step = "select_vendor"
            st.rerun()
