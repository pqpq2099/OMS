import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

# =========================
# 1. 核心設定
# =========================
SHEET_ID = '1c9twPCyOumPKSau5xgUShJJAG-D9aaZBhK2FWBl2zwc' 

# 💡 嚴格定義中文欄位名稱
COL_MAP = {
    'record_date': '日期',
    'store_name': '店名',
    'vendor_name': '廠商',
    'item_name': '品項',
    'last_stock': '上次剩餘',
    'last_purchase': '上次叫貨',
    'this_stock': '本次剩餘',
    'this_purchase': '本次叫貨',
    'usage_qty': '期間消耗',
    'unit_price': '單價',
    'total_price': '總金額'
}

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
        st.error(f"⚠️ 金鑰讀取失敗: {e}"); return None

def get_cloud_data():
    try:
        client = get_gspread_client()
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet("Records")
        df = pd.DataFrame(ws.get_all_records())
        # 強制數值轉換，避免雲端髒資料干擾
        for col in [COL_MAP['this_stock'], COL_MAP['this_purchase'], COL_MAP['unit_price'], COL_MAP['total_price']]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

def sync_to_cloud(df_to_save):
    client = get_gspread_client()
    if not client: return False
    try:
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet("Records")
        headers = list(COL_MAP.values())
        # 強制校準標題列
        ws.update('A1', [headers]) 
        ws.append_rows(df_to_save.values.tolist())
        return True
    except Exception as e:
        st.error(f"❌ 雲端寫入失敗: {e}"); return False

# =========================
# 2. 檔案載入
# =========================
CSV_STORE = Path("品項總覽.xlsx - 分店.csv")
CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv")

def load_csv_safe(path):
    for enc in ['utf-8', 'cp950', 'big5', 'utf-8-sig']:
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
    st.session_state.record_date = st.date_input("🗓️ 紀錄/送貨日期", value=st.session_state.record_date)
    
    col_v, col_r = st.columns([2, 1])
    with col_v:
        st.subheader("廠商列表")
        vendors = sorted(df_i['廠商名稱'].unique())
        for v in vendors:
            if st.button(f"📦 {v}", use_container_width=True):
                st.session_state.vendor = v
                st.session_state.history_df = get_cloud_data()
                st.session_state.step = "fill_items"
                st.rerun()
    
    with col_r:
        st.subheader("功能選單")
        if st.button("📄 產生今日叫貨報表", type="primary", use_container_width=True):
            st.session_state.history_df = get_cloud_data()
            st.session_state.step = "export"
            st.rerun()
        if st.button("📊 期間分析查詢", use_container_width=True):
            st.session_state.history_df = get_cloud_data()
            st.session_state.step = "analysis"
            st.rerun()
        if st.button("⬅️ 返回分店列表", use_container_width=True):
            st.session_state.step = "select_store"
            st.rerun()

elif st.session_state.step == "fill_items":
    st.title(f"📝 {st.session_state.vendor}")
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    with st.form("inventory_form"):
        temp_data = []
        for _, row in items.iterrows():
            # 💡 這裡必須與 CSV 的標題完全一致
            name = row['品項名稱'] 
            try:
                price = float(row['單價'])
            except:
                price = 0.0
            
            prev_s, prev_p = 0, 0
            if not hist_df.empty:
                # 💡 比對試算表中的「店名」與「品項」
                past = hist_df[(hist_df[COL_MAP['store_name']] == st.session_state.store) & 
                               (hist_df[COL_MAP['item_name']] == name)]
                if not past.empty:
                    latest = past.iloc[-1]
                    prev_s = int(float(latest.get(COL_MAP['this_stock'], 0)))
                    prev_p = int(float(latest.get(COL_MAP['this_purchase'], 0)))
            
            st.write(f"---")
            st.markdown(f"**{name}**")
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                st.info(f"上次結餘：{prev_s + prev_p}")
                t_s = st.number_input(f"這次剩餘", min_value=0, step=1, key=f"s_{name}")
            with c2:
                t_p = st.number_input(f"這次叫貨", min_value=0, step=1, key=f"p_{name}")
            with c3:
                usage = (prev_s + prev_p) - t_s
                st.success(f"計算使用量：{usage}")
            
            total_amt = t_p * price
            if t_s > 0 or t_p >
