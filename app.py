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
        st.error(f"⚠️ 金鑰讀取失敗: {e}"); return None

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
# 2. 檔案載入
# =========================
CSV_STORE = Path("品項總覽.xlsx - 分店.csv")
CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv")

def load_csv_safe(path):
    for enc in ['utf-8-sig', 'utf-8', 'cp950', 'big5']:
        try:
            df = pd.read_csv(path, encoding=enc)
            df.columns = [str(c).strip().replace('\ufeff', '') for c in df.columns]
            return df.map(lambda x: str(x).strip() if isinstance(x, str) else x)
        except: continue
    return None

# 💡 這裡將佈局設為寬廣模式，並加入自定義 CSS 強制手機版不換行
st.set_page_config(page_title="OMS 進銷存系統", layout="wide")

st.markdown("""
    <style>
    /* 強制 columns 在手機上不垂直堆疊 */
    [data-testid="column"] {
        min-width: 0px !important;
        flex-basis: auto !important;
    }
    /* 縮小輸入框間距 */
    .stNumberInput {
        padding-bottom: 0px !important;
    }
    </style>
    """, unsafe_allow_html=True)

df_s, df_i = load_csv_safe(CSV_STORE), load_csv_safe(CSV_ITEMS)

if df_i is None or '品項' not in df_i.columns:
    st.error("❌ CSV 缺少 '品項' 欄位"); st.stop()

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
            if st.button(f"📍 {s}", key=f"btn_{s}", use_container_width=True):
                st.session_state.store = s; st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "select_vendor":
    st.title(f"🏢 {st.session_state.store}")
    st.session_state.record_date = st.date_input("🗓️ 日期", value=st.session_state.record_date)
    v_col = '廠商名稱' if '廠商名稱' in df_i.columns else '廠商'
    vendors = sorted(df_i[v_col].unique())
    for v in vendors:
        if st.button(f"📦 {v}", key=f"v_{v}", use_container_width=True):
            st.session_state.vendor = v; st.session_state.history_df = get_cloud_data()
            st.session_state.step = "fill_items"; st.rerun()
    st.write("---")
    if st.button("📄 產生叫貨報表", type="primary", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "export"; st.rerun()
    if st.button("📊 期間分析", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "analysis"; st.rerun()
    if st.button("⬅️ 返回分店", use_container_width=True): st.session_state.step = "select_store"; st.rerun()

elif st.session_state.step == "fill_items":
    st.title(f"📝 {st.session_state.vendor}")
    v_col = '廠商名稱' if '廠商名稱' in df_i.columns else '廠商'
    items = df_i[df_i[v_col] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    # 💡 頂部標題區：使用比例分配，對齊手機螢幕
    h1, h2, h3 = st.columns([2, 1, 1])
    h1.write("**品項**")
    h2.write("**剩餘**")
    h3.write("**叫貨**")
    st.write("---")

    with st.form("inventory_form"):
        temp_data = []
        for _, row in items.iterrows():
            full_name = str(row['品項']).strip()
            display_name = item_display_map.get(full_name, full_name)
            unit = str(row['單位']).strip() if '單位' in row else ""
            price = pd.to_numeric(row.get('單價', 0), errors='coerce')
            
            # 歷史庫存抓取
            prev_s, prev_p = 0, 0
            if not hist_df.empty:
                past = hist_df[(hist_df[COL_MAP['store_name']] == st.session_state.store) & (hist_df[COL_MAP['item_name']] == full_name)]
                if not past.empty:
                    latest = past.iloc[-1]
                    prev_s = int(pd.to_numeric(latest.get(COL_MAP['this_stock'], 0), errors='coerce') or 0)
                    prev_p = int(pd.to_numeric(latest.get(COL_MAP['this_purchase'], 0), errors='coerce') or 0)
            
            # 💡 強制橫向排版
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                st.markdown(f"**{display_name}**")
                st.caption(f"{unit} (前:{prev_s+prev_p})")
            with c2:
                t_s = st.number_input("剩", min_value=0, step=1, key=f"s_{full_name}", label_visibility="collapsed")
            with c3:
                t_p = st.number_input("叫", min_value=0, step=1, key=f"p_{full_name}", label_visibility="collapsed")
            
            usage = (prev_s + prev_p) - t_s
            if t_s > 0 or t_p > 0:
                temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, full_name, unit, int(prev_s), int(prev_p), int(t_s), int(t_p), int(usage), float(price), float(round(t_p * price, 1))])
        
        st.write("---")
        if st.form_submit_button("💾 儲存同步", use_container_width=True):
            if temp_data and sync_to_cloud(pd.DataFrame(temp_data)):
                st.success("✅ 成功！"); st.session_state.step = "select_vendor"; st.rerun()
            else: st.warning("請輸入數值")
        if st.form_submit_button("❌ 返回", use_container_width=True):
            st.session_state.step = "select_vendor"; st.rerun()

# (其餘 export 與 analysis 部分保持不變...)
elif st.session_state.step == "export":
    st.title("📋 叫貨報表")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    date_str = str(st.session_state.record_date)
    if not hist_df.empty:
        hist_df[COL_MAP['record_date']] = hist_df[COL_MAP['record_date']].astype(str)
        recs = hist_df[(hist_df[COL_MAP['store_name']] == st.session_state.store) & (hist_df[COL_MAP['record_date']] == date_str) & (pd.to_numeric(hist_df[COL_MAP['this_purchase']], errors='coerce') > 0)].copy()
        if recs.empty: st.warning("無紀錄")
        else:
            output = f"{date_str}\n{st.session_state.store}\n"
            for v in recs[COL_MAP['vendor_name']].unique():
                output += f"\n{v}\n"
                for _, r in recs[recs[COL_MAP['vendor_name']] == v].iterrows():
                    disp_n = item_display_map.get(r[COL_MAP['item_name']], r[COL_MAP['item_name']])
                    u, p, q = r[COL_MAP['unit']], int(pd.to_numeric(r[COL_MAP['unit_price']], errors='coerce') or 0), int(pd.to_numeric(r[COL_MAP['this_purchase']], errors='coerce') or 0)
                    output += f"● {disp_n} ( {u} )-${p}：{q}{u}\n"
            st.text_area("📱 LINE 複製格式", value=output, height=300)
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "analysis":
    st.title("📊 進銷存分析")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    start = st.date_input("起始", value=date.today()-timedelta(7))
    end = st.date_input("結束", value=date.today())
    if not hist_df.empty:
        hist_df[COL_MAP['record_date']] = pd.to_datetime(hist_df[COL_MAP['record_date']]).dt.date
        analysis = hist_df[(hist_df[COL_MAP['store_name']] == st.session_state.store) & (hist_df[COL_MAP['record_date']] >= start) & (hist_df[COL_MAP['record_date']] <= end)].copy()
        if not analysis.empty:
            analysis['顯示名稱'] = analysis[COL_MAP['item_name']].map(lambda x: item_display_map.get(x, x))
            summary = analysis.groupby([COL_MAP['vendor_name'], '顯示名稱', COL_MAP['unit'], COL_MAP['unit_price']]).agg({COL_MAP['usage_qty']: 'sum', COL_MAP['total_price']: 'sum'}).reset_index()
            st.dataframe(summary, use_container_width=True)
            st.metric("採購支出", f"${summary[COL_MAP['total_price']].sum():,.0f}")
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()
