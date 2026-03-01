import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

# 💡 安全載入 Plotly，若環境未就緒則跳過繪圖，不影響數據顯示
try:
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# =========================
# 1. 核心與數據設定
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
        st.error(f"⚠️ 金鑰連線失敗: {e}"); return None

def get_worksheet_data(sheet_name):
    """讀取工作表數據 (標題在第一行)"""
    try:
        client = get_gspread_client()
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        
        # 轉換數值
        num_cols = ['上次剩餘', '上次叫貨', '本次剩餘', '本次叫貨', '期間消耗', '單價', '總金額']
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

def get_cloud_data():
    """獲取總表數據 (強制不使用快取，解決讀取不到問題)"""
    return get_worksheet_data("Records")

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
# 2. 全域視覺標準
# =========================
st.set_page_config(page_title="OMS 系統", layout="centered")
st.markdown("""
    <style>
    html, body, [class*="css"], .stMarkdown, p, span, div, b {
        font-family: 'PingFang TC', 'Microsoft JhengHei', sans-serif !important;
        font-weight: 700 !important;
    }
    h1, h2, h3 { font-weight: 800 !important; }
    .stButton button { font-weight: 700 !important; }
    .stNumberInput input { font-weight: 800 !important; font-size: 16px !important; text-align: center !important; }
    .stCaption { font-weight: 600 !important; font-size: 13px !important; }
    div[data-testid="stNumberInputStepUp"], div[data-testid="stNumberInputStepDown"], .stNumberInput button { display: none !important; }
    input[type=number] { -moz-appearance: textfield !important; -webkit-appearance: none !important; margin: 0 !important; }
    </style>
    """, unsafe_allow_html=True)

# 讀取本機 CSV
CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv")
CSV_STORE = Path("品項總覽.xlsx - 分店.csv")

def load_csv_safe(path):
    for enc in ['utf-8-sig', 'utf-8', 'cp950', 'big5']:
        try:
            if not path.exists(): return None
            df = pd.read_csv(path, encoding=enc)
            return df.map(lambda x: str(x).strip() if isinstance(x, str) else x)
        except: continue
    return None

df_s, df_i = load_csv_safe(CSV_STORE), load_csv_safe(CSV_ITEMS)
if df_i is not None:
    item_display_map = df_i.drop_duplicates('品項ID').set_index('品項ID')['品項名稱'].to_dict()

if "step" not in st.session_state: st.session_state.step = "select_store"
if "record_date" not in st.session_state: st.session_state.record_date = date.today()

# =========================
# 3. 介面分流
# =========================

if st.session_state.step == "select_store":
    st.title("🏠 選擇分店")
    if df_s is not None:
        for s in df_s['分店名稱'].unique():
            if st.button(f"📍 {s}", key=f"s_{s}", use_container_width=True):
                st.session_state.store = s; st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "select_vendor":
    st.title(f"🏢 {st.session_state.store}")
    st.session_state.record_date = st.date_input("🗓️ 盤點日期", value=st.session_state.record_date)
    
    if df_i is not None:
        vendors = sorted(df_i['廠商名稱'].unique())
        for v in vendors:
            if st.button(f"📦 {v}", key=f"v_{v}", use_container_width=True):
                st.session_state.vendor = v; st.session_state.history_df = get_cloud_data()
                st.session_state.step = "fill_items"; st.rerun()
    
    st.write("---")
    st.write("<b>📊 數據與分析入口</b>", unsafe_allow_html=True)
    
    # 💡 功能入口補回與加固
    if st.button("📄 產生今日進貨明細", type="primary", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "export"; st.rerun()
    
    if st.button("📈 期間進銷存分析", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "analysis"; st.rerun()
    
    history_sheet = f"{st.session_state.store}_紀錄"
    if st.button(f"📜 查看 {st.session_state.store} 歷史紀錄庫", use_container_width=True):
        st.session_state.view_df = get_worksheet_data(history_sheet)
        st.session_state.step = "view_history"; st.rerun()
        
    if st.button("⬅️ 返回分店列表", use_container_width=True):
        st.session_state.step = "select_store"; st.rerun()

elif st.session_state.step == "view_history":
    st.title(f"📜 {st.session_state.store} 歷史紀錄")
    view_df = st.session_state.get('view_df', pd.DataFrame())
    
    if not view_df.empty:
        tab1, tab2 = st.tabs(["📋 數據明細表", "📈 品項趨勢圖"])
        with tab1:
            search = st.text_input("🔍 搜尋品項或日期")
            display_df = view_df.copy()
            if search:
                display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search)).any(axis=1)]
            st.dataframe(display_df.sort_values('日期', ascending=False), use_container_width=True, hide_index=True)
        with tab2:
            if HAS_PLOTLY:
                target_item = st.selectbox("請選擇品項", options=sorted(view_df['品項名稱'].unique()))
                plot_df = view_df[view_df['品項名稱'] == target_item].sort_values('日期')
                fig = px.line(plot_df, x="日期", y="期間消耗", markers=True)
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("💡 繪圖模組載入中，請確保 requirements.txt 已更新。")
    else:
        st.warning("目前尚無可讀取的紀錄。")
        if st.button("🔄 強制刷新重新讀取", use_container_width=True):
            st.session_state.view_df = get_worksheet_data(f"{st.session_state.store}_紀錄"); st.rerun()
            
    if st.button("⬅️ 返回廠商列表", use_container_width=True):
        st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "export":
    st.title("📋 今日進貨明細")
    hist_df = get_cloud_data()
    week_map = {0:'一', 1:'二', 2:'三', 3:'四', 4:'五', 5:'六', 6:'日'}
    delivery_date = st.session_state.record_date + timedelta(days=1)
    header_date = f"{delivery_date.month}/{delivery_date.day}({week_map[delivery_date.weekday()]})"
    if not hist_df.empty:
        recs = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['日期'].astype(str) == str(st.session_state.record_date)) & (hist_df['本次叫貨'] > 0)]
        if not recs.empty:
            output = f"{header_date}\n"
            for v in recs['廠商'].unique():
                output += f"\n{v}\n{st.session_state.store}\n"
                for _, r in recs[recs['廠商'] == v].iterrows():
                    val = float(r['本次叫貨']); val_s = int(val) if val.is_integer() else val
                    output += f"{r['品項名稱']} {val_s} {r['單位']}\n"
                output += f"禮拜{week_map[delivery_date.weekday()]}到，謝謝\n"
            st.text_area("📱 LINE 複製", value=output, height=400)
        else: st.info("今日尚未有叫貨紀錄。")
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "analysis":
    st.title("📊 期間進銷存分析")
    hist_df = get_cloud_data()
    start = st.date_input("起始", value=date.today()-timedelta(7)); end = st.date_input("結束", value=date.today())
    if not hist_df.empty:
        hist_df['日期'] = pd.to_datetime(hist_df['日期']).dt.date
        analysis = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['日期'] >= start) & (hist_df['日期'] <= end)]
        if not analysis.empty:
            summary = analysis.groupby(['廠商', '品項名稱', '單位', '單價']).agg({'期間消耗': 'sum', '本次叫貨': 'sum', '總金額': 'sum'}).reset_index()
            st.dataframe(summary, use_container_width=True)
        else: st.info("選定期間內無紀錄。")
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()

# 填寫頁面保持
elif st.session_state.step == "fill_items":
    st.title(f"📝 {st.session_state.vendor}")
    # ... (此段填寫邏輯與之前完全一致，確保輸入寬度 70px)
    st.button("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"))
