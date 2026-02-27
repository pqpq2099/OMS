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
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        # 💡 強制確保金額欄位為數字類型
        for col in [COL_MAP['unit_price'], COL_MAP['total_price']]:
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
        # 確保標題列存在
        headers = list(COL_MAP.values())
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
# 3. 介面流程控制
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
    st.caption(f"分店：{st.session_state.store} | 日期：{st.session_state.record_date}")
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    with st.form("inventory_form"):
        temp_data = []
        for _, row in items.iterrows():
            name = row['品項名稱']
            price = float(row.get('單價', 0))
            
            prev_s, prev_p = 0, 0
            if not hist_df.empty:
                past = hist_df[(hist_df[COL_MAP['store_name']] == st.session_state.store) & (hist_df[COL_MAP['item_name']] == name)]
                if not past.empty:
                    latest = past.iloc[-1]
                    prev_s, prev_p = int(float(latest[COL_MAP['this_stock']])), int(float(latest[COL_MAP['this_purchase']]))
            
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
            if t_s > 0 or t_p > 0:
                temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, name, int(prev_s), int(prev_p), int(t_s), int(t_p), int(usage), float(price), float(total_amt)])
        
        if st.form_submit_button("💾 儲存並返回廠商列表", use_container_width=True):
            if temp_data:
                df_to_save = pd.DataFrame(temp_data)
                if sync_to_cloud(df_to_save):
                    st.success("✅ 雲端同步成功！")
                    st.session_state.step = "select_vendor"; st.rerun()
            else: st.warning("未填寫數據。")

elif st.session_state.step == "export":
    date_str = str(st.session_state.record_date)
    st.title(f"📋 {date_str} 叫貨報表")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    if not hist_df.empty:
        hist_df[COL_MAP['record_date']] = hist_df[COL_MAP['record_date']].astype(str)
        recs = hist_df[(hist_df[COL_MAP['store_name']] == st.session_state.store) & 
                       (hist_df[COL_MAP['record_date']] == date_str) & 
                       (hist_df[COL_MAP['this_purchase']] > 0)]
        
        if recs.empty:
            st.warning(f"{date_str} 目前沒有任何叫貨紀錄。")
        else:
            st.subheader("🔍 今日叫貨數據對照表")
            display_cols = {COL_MAP['vendor_name']: '廠商', COL_MAP['item_name']: '品項名稱', 
                            COL_MAP['last_stock']: '上次庫存', COL_MAP['last_purchase']: '上次叫貨', 
                            COL_MAP['this_stock']: '這次剩餘', COL_MAP['usage_qty']: '期間使用量', 
                            COL_MAP['this_purchase']: '本次叫貨量', COL_MAP['total_price']: '總金額'}
            st.table(recs[list(display_cols.keys())].rename(columns=display_cols))
            
            output = f"【{st.session_state.store}】叫貨單 ({date_str})\n--------------------\n"
            for v in recs[COL_MAP['vendor_name']].unique():
                output += f"\n廠商：{v}\n"
                for _, r in recs[recs[COL_MAP['vendor_name']] == v].iterrows():
                    output += f"● {r[COL_MAP['item_name']]}：{int(r[COL_MAP['this_purchase']])}\n"
            st.subheader("📱 LINE 複製格式")
            st.text_area("全選複製：", value=output, height=300)
    
    if st.button("⬅️ 返回廠商列表"): st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "analysis":
    st.title("📊 期間使用量彙整")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    c1, c2 = st.columns(2)
    start, end = c1.date_input("起始日", value=date.today()-timedelta(7)), c2.date_input("結束日", value=date.today())
    
    if not hist_df.empty:
        hist_df[COL_MAP['record_date']] = pd.to_datetime(hist_df[COL_MAP['record_date']]).dt.date
        analysis = hist_df[(hist_df[COL_MAP['store_name']] == st.session_state.store) & 
                           (hist_df[COL_MAP['record_date']] >= start) & 
                           (hist_df[COL_MAP['record_date']] <= end)]
        if not analysis.empty:
            summary = analysis.groupby([COL_MAP['vendor_name'], COL_MAP['item_name']]).agg({
                COL_MAP['usage_qty']: 'sum',
                COL_MAP['total_price']: 'sum'
            }).reset_index()
            summary.columns = ['廠商名稱', '品項名稱', '總消耗數量', '總金額']
            st.table(summary[summary['總消耗數量'] != 0].sort_values('總消耗數量', ascending=False))
        else: st.info("期間無數據。")
    if st.button("⬅️ 返回廠商列表"): st.session_state.step = "select_vendor"; st.rerun()
