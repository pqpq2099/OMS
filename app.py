import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

# =========================
# 1. 核心設定 (數據庫對應)
# =========================
SHEET_ID = '1c9twPCyOumPKSau5xgUShJJAG-D9aaZBhK2FWBl2zwc' 

COL_MAP = {
    'record_date': '日期',
    'store_name': '店名',
    'vendor_name': '廠商',
    'item_key': '品項',       # 數據庫唯一識別(長名)
    'item_display': '品項名稱', 
    'unit': '單位',
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
        st.error(f"⚠️ 金鑰錯誤: {e}"); return None

def get_cloud_data():
    try:
        client = get_gspread_client()
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet("Records")
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

def sync_to_cloud(df_to_save):
    client = get_gspread_client()
    if not client: return False
    try:
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet("Records")
        ws.append_rows(df_to_save.values.tolist())
        return True
    except: return False

# =========================
# 2. 佈局樣式控制 (強制橫向與移除按鈕)
# =========================
st.set_page_config(page_title="OMS 進銷存系統", layout="centered")

st.markdown("""
    <style>
    /* 1. 徹底拔除數字輸入框的 + 與 - 按鈕 */
    button[step="1"], .stNumberInput button { display: none !important; }
    div[data-testid="stNumberInputStepUp"], div[data-testid="stNumberInputStepDown"] {
        display: none !important;
    }
    
    /* 2. 手機版強制橫向排版 (不換行) */
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
    }
    [data-testid="column"] {
        min-width: 0px !important;
        flex: 1 1 auto !important;
    }
    div[data-testid="column"]:nth-of-type(1) { flex: 3 !important; }
    div[data-testid="column"]:nth-of-type(2) { flex: 1.2 !important; }
    div[data-testid="column"]:nth-of-type(3) { flex: 1.2 !important; }

    /* 3. 移除標籤並讓輸入框對齊 */
    div[data-testid="stNumberInput"] label { display: none !important; }
    .stNumberInput input {
        font-size: 16px !important;
        padding: 5px !important;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

CSV_STORE = Path("品項總覽.xlsx - 分店.csv")
CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv")

def load_csv_safe(path):
    for enc in ['utf-8-sig', 'utf-8', 'cp950', 'big5']:
        try:
            df = pd.read_csv(path, encoding=enc)
            df.columns = [str(c).strip() for c in df.columns]
            return df.map(lambda x: str(x).strip() if isinstance(x, str) else x)
        except: continue
    return None

df_s, df_i = load_csv_safe(CSV_STORE), load_csv_safe(CSV_ITEMS)
if df_i is None: st.error("❌ 品項檔讀取失敗"); st.stop()

# 名稱映射字典
item_display_map = df_i.set_index('品項')['品項名稱'].to_dict()

if "step" not in st.session_state: st.session_state.step = "select_store"
if "record_date" not in st.session_state: st.session_state.record_date = date.today()

# =========================
# 3. 介面流程
# =========================

if st.session_state.step == "select_store":
    st.title("🏠 選擇分店")
    if df_s is not None:
        col_s = '分店名稱' if '分店名稱' in df_s.columns else df_s.columns[0]
        for s in df_s[col_s].unique():
            if st.button(f"📍 {s}", key=f"s_{s}", use_container_width=True):
                st.session_state.store = s; st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "select_vendor":
    st.title(f"🏢 {st.session_state.store}")
    st.session_state.record_date = st.date_input("🗓️ 盤點日期", value=st.session_state.record_date)
    v_col = '廠商名稱' if '廠商名稱' in df_i.columns else '廠商'
    vendors = sorted(df_i[v_col].unique())
    for v in vendors:
        if st.button(f"📦 {v}", key=f"v_{v}", use_container_width=True):
            st.session_state.vendor = v; st.session_state.history_df = get_cloud_data()
            st.session_state.step = "fill_items"; st.rerun()
    st.write("---")
    if st.button("📄 產生今日進貨明細表", type="primary", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "export"; st.rerun()
    if st.button("📊 期間進銷存分析", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "analysis"; st.rerun()
    if st.button("⬅️ 返回分店列表", use_container_width=True):
        st.session_state.step = "select_store"; st.rerun()

elif st.session_state.step == "fill_items":
    st.title(f"📝 {st.session_state.vendor}")
    v_col = '廠商名稱' if '廠商名稱' in df_i.columns else '廠商'
    items = df_i[df_i[v_col] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    # 橫向表頭
    h1, h2, h3 = st.columns([3, 1.2, 1.2])
    h1.write("**品項**")
    h2.write("**庫存**")
    h3.write("**進貨**")
    st.write("---")

    with st.form("inventory_form"):
        temp_data = []
        for _, row in items.iterrows():
            f_n = str(row['品項']).strip()
            d_n = item_display_map.get(f_n, f_n)
            unit = str(row['單位']).strip() if '單位' in row else ""
            price = pd.to_numeric(row.get('單價', 0), errors='coerce')
            
            p_s, p_p = 0, 0
            if not hist_df.empty:
                past = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['品項'] == f_n)]
                if not past.empty:
                    latest = past.iloc[-1]
                    p_s = int(pd.to_numeric(latest.get('本次剩餘', 0), errors='coerce') or 0)
                    p_p = int(pd.to_numeric(latest.get('本次叫貨', 0), errors='coerce') or 0)
            
            # 💡 橫向排版列
            c1, c2, c3 = st.columns([3, 1.2, 1.2])
            with c1:
                st.markdown(f"**{d_n}**")
                st.caption(f"{unit} (上次結餘:{p_s+p_p})")
            with c2:
                t_s = st.number_input("庫", min_value=0, step=1, key=f"s_{f_n}")
            with c3:
                t_p = st.number_input("進", min_value=0, step=1, key=f"p_{f_n}")
            
            usage = (p_s + p_p) - t_s
            temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, f_n, d_n, unit, int(p_s), int(p_p), int(t_s), int(t_p), int(usage), float(price), float(round(t_p * price, 1))])

        if st.form_submit_button("💾 儲存並同步", use_container_width=True):
            valid = [d for d in temp_data if d[8] > 0 or d[9] > 0]
            if valid and sync_to_cloud(pd.DataFrame(valid)):
                st.success("✅ 儲存成功 (期間消耗已結算)"); st.session_state.step = "select_vendor"; st.rerun()
    
    if st.button("⬅️ 返回廠商列表", use_container_width=True):
        st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "export":
    st.title("📋 今日進貨報表")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    date_str = str(st.session_state.record_date)
    if not hist_df.empty:
        hist_df['日期'] = hist_df['日期'].astype(str)
        recs = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['日期'] == date_str) & (pd.to_numeric(hist_df['本次叫貨'], errors='coerce') > 0)].copy()
        
        if recs.empty: st.warning("今日無進貨數據")
        else:
            # 💡 報表格式修正：無單價、無總金額，純顯示品項與進貨量
            output = f"【{st.session_state.store}】進貨單 ({date_str})\n"
            for v in recs['廠商'].unique():
                output += f"\n{v}\n"
                for _, r in recs[recs['廠商'] == v].iterrows():
                    d_n = r.get('品項名稱', item_display_map.get(r['品項'], r['品項']))
                    u, q = r['單位'], int(pd.to_numeric(r['本次叫貨'], errors='coerce') or 0)
                    output += f"● {d_n}：{q}{u}\n"
            st.text_area("📱 LINE 複製格式", value=output, height=300)
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "analysis":
    st.title("📊 期間進銷存分析")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    c1, c2 = st.columns(2)
    start, end = c1.date_input("起始", value=date.today()-timedelta(7)), c2.date_input("結束", value=date.today())
    if not hist_df.empty:
        hist_df['日期'] = pd.to_datetime(hist_df['日期']).dt.date
        analysis = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['日期'] >= start) & (hist_df['日期'] <= end)].copy()
        if not analysis.empty:
            # 💡 分析顯示
            summary = analysis.groupby(['廠商', '品項名稱', '單位']).agg({'期間消耗': 'sum', '本次叫貨': 'sum'}).reset_index()
            # 獲取最後庫存
            last_recs = analysis.sort_values('日期').groupby('品項名稱').tail(1)
            stock_map = last_recs.set_index('品項名稱')['本次剩餘'].to_dict()
            summary['期末庫存'] = summary['品項名稱'].map(stock_map).fillna(0).astype(int)
            st.dataframe(summary, use_container_width=True)
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()
