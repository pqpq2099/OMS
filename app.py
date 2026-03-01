import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

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
    """讀取工作表：直接從第一行開始讀取 (配合您的結構調整)"""
    try:
        client = get_gspread_client()
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet(sheet_name)
        # 💡 使用 get_all_records，假設標題就在第一行
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        
        num_cols = ['上次剩餘', '上次叫貨', '本次剩餘', '本次叫貨', '期間消耗', '單價', '總金額']
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df
    except Exception as e:
        # 如果 get_all_records 失敗 (可能因為公式報錯)，改用 get_all_values
        try:
            data = ws.get_all_values()
            if len(data) > 1:
                df = pd.DataFrame(data[1:], columns=data[0])
                return df
        except: pass
        return pd.DataFrame()

def get_cloud_data():
    return get_worksheet_data("Records")

# =========================
# 2. 全域視覺標準
# =========================
st.set_page_config(page_title="OMS 系統", layout="centered")
st.markdown("""
    <style>
    html, body, [class*="css"], .stMarkdown, p, span, div, b {
        font-family: 'PingFang TC', 'Microsoft JhengHei', sans-serif !important;
        font-weight: 700 !important;
        font-style: normal !important;
    }
    h1, h2, h3 { font-weight: 800 !important; }
    .stNumberInput input { font-weight: 800 !important; font-size: 16px !important; text-align: center !important; }
    div[data-testid="stNumberInputStepUp"], div[data-testid="stNumberInputStepDown"], .stNumberInput button { display: none !important; }
    input[type=number] { -moz-appearance: textfield !important; -webkit-appearance: none !important; margin: 0 !important; }
    </style>
    """, unsafe_allow_html=True)

# 讀取品項清單
CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv")
CSV_STORE = Path("品項總覽.xlsx - 分店.csv")

def load_csv_safe(path):
    for enc in ['utf-8-sig', 'utf-8', 'cp950', 'big5']:
        try:
            df = pd.read_csv(path, encoding=enc)
            return df.map(lambda x: str(x).strip() if isinstance(x, str) else x)
        except: continue
    return None

df_s, df_i = load_csv_safe(CSV_STORE), load_csv_safe(CSV_ITEMS)
if df_i is not None:
    item_display_map = df_i.drop_duplicates('品項ID').set_index('品項ID')['品項名稱'].to_dict()

if "step" not in st.session_state: st.session_state.step = "select_store"
if "record_date" not in st.session_state: st.session_state.record_date = date.today()

# --- 核心頁面跳轉邏輯 ---
if st.session_state.step == "select_store":
    st.title("🏠 選擇分店")
    if df_s is not None:
        for s in df_s['分店名稱'].unique():
            if st.button(f"📍 {s}", key=f"s_{s}", use_container_width=True):
                st.session_state.store = s; st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "select_vendor":
    st.title(f"🏢 {st.session_state.store}")
    st.session_state.record_date = st.date_input("🗓️ 盤點日期", value=st.session_state.record_date)
    
    # 廠商列表
    if df_i is not None:
        vendors = sorted(df_i['廠商名稱'].unique())
        for v in vendors:
            if st.button(f"📦 {v}", key=f"v_{v}", use_container_width=True):
                st.session_state.vendor = v; st.session_state.history_df = get_cloud_data()
                st.session_state.step = "fill_items"; st.rerun()
    
    st.write("---")
    # 💡 歷史紀錄入口
    history_sheet = f"{st.session_state.store}_紀錄"
    if st.button(f"📜 查看 {st.session_state.store} 歷史紀錄", use_container_width=True):
        st.session_state.view_df = get_worksheet_data(history_sheet)
        st.session_state.step = "view_history"; st.rerun()

    if st.button("⬅️ 返回分店列表", use_container_width=True):
        st.session_state.step = "select_store"; st.rerun()

elif st.session_state.step == "view_history":
    st.title(f"📜 {st.session_state.store} 歷史紀錄")
    view_df = st.session_state.get('view_df', pd.DataFrame())
    if not view_df.empty:
        # 💡 系統內建最強搜尋框
        search = st.text_input("🔍 搜尋品項或日期 (即時過濾)", help="輸入名稱或日期，系統會自動幫您找。")
        display_df = view_df.copy()
        if search:
            display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search)).any(axis=1)]
        st.dataframe(display_df.sort_values('日期', ascending=False), use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ 無法顯示紀錄，請確認該分店分頁標題是否已拉到第一行，且公式無報錯。")
    if st.button("⬅️ 返回廠商列表", use_container_width=True):
        st.session_state.step = "select_vendor"; st.rerun()
