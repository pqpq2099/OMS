import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

# =========================
# 1. 核心數據引擎
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
        st.error(f"⚠️ 連線失敗: {e}"); return None

def get_worksheet_data(sheet_name):
    try:
        client = get_gspread_client()
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

# =========================
# 2. 全域視覺鎖定 (修正重疊與分行)
# =========================
st.set_page_config(page_title="OMS 系統", layout="centered")
st.markdown("""
    <style>
    /* 1. 字體鎖定 */
    html, body, [class*="css"], .stMarkdown, p, span, div, b {
        font-family: 'PingFang TC', 'Microsoft JhengHei', sans-serif !important;
        font-weight: 700 !important;
    }
    
    /* 2. 徹底消滅輸入框幽靈文字與重疊 */
    div[data-testid="stTextInput"] label,
    div[data-testid="stWidgetLabel"],
    [aria-label] {
        display: none !important;
        height: 0px !important;
        visibility: hidden !important;
    }

    /* 3. 強制單排：壓縮文字框樣式並鎖定寬度 */
    .stTextInput input {
        font-weight: 800 !important;
        font-size: 16px !important;
        text-align: center !important;
        padding: 4px 2px !important;
        height: 38px !important;
        min-width: 65px !important; /* 💡 鎖定格子最小寬度 */
    }

    /* 4. 欄位間距極小化，防止換行觸發 */
    div[data-testid="stHorizontalBlock"] {
        gap: 0.1rem !important;
        display: flex !important;
        flex-direction: row !important; /* 💡 強制橫排，不准塌陷 */
        flex-wrap: nowrap !important;
    }
    
    /* 5. 分店與廠商按鈕保持大面積好點擊 */
    .stButton button { width: 100% !important; border-radius: 8px !important; }
    </style>
    """, unsafe_allow_html=True)

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

if "step" not in st.session_state: st.session_state.step = "select_store"
if "record_date" not in st.session_state: st.session_state.record_date = date.today()

# =========================
# 3. 介面流程
# =========================

# --- 分店選擇頁 ---
if st.session_state.step == "select_store":
    st.title("🏠 選擇分店")
    if df_s is not None:
        for s in df_s['分店名稱'].unique():
            if st.button(f"📍 {s}", key=f"s_{s}"):
                st.session_state.store = s; st.session_state.step = "select_vendor"; st.rerun()

# --- 廠商中心 ---
elif st.session_state.step == "select_vendor":
    st.title(f"🏢 {st.session_state.store}")
    st.session_state.record_date = st.date_input("🗓️ 盤點日期", value=st.session_state.record_date)
    st.write("<b>📦 廠商</b>", unsafe_allow_html=True)
    
    if df_i is not None:
        vendors = sorted(df_i['廠商名稱'].unique())
        # 手機雙欄廠商穩定顯示
        for i in range(0, len(vendors), 2):
            cols = st.columns(2)
            with cols[0]:
                if st.button(vendors[i], key=f"v_{vendors[i]}"):
                    st.session_state.vendor = vendors[i]
                    st.session_state.history_df = get_worksheet_data("Records")
                    st.session_state.step = "fill_items"; st.rerun()
            if i + 1 < len(vendors):
                with cols[1]:
                    if st.button(vendors[i+1], key=f"v_{vendors[i+1]}"):
                        st.session_state.vendor = vendors[i+1]
                        st.session_state.history_df = get_worksheet_data("Records")
                        st.session_state.step = "fill_items"; st.rerun()
    st.write("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📄 產生叫貨明細", type="primary"):
            st.session_state.history_df = get_worksheet_data("Records"); st.session_state.step = "export"; st.rerun()
    with c2:
        if st.button("📈 進銷存分析"):
            st.session_state.history_df = get_worksheet_data("Records"); st.session_state.step = "analysis"; st.rerun()
    if st.button("⬅️ 返回分店"): st.session_state.step = "select_store"; st.rerun()

# --- 進貨填寫頁 (關鍵修正區) ---
elif st.session_state.step == "fill_items":
    if "vendor" not in st.session_state: st.session_state.step = "select_vendor"; st.rerun()
    st.markdown("<style>.block-container { padding-left: 0.1rem !important; padding-right: 0.1rem !important; }</style>", unsafe_allow_html=True)
    st.title(f"📝 {st.session_state.vendor}")
    
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    # 💡 標題列分配：5 : 2 : 2
    h1, h2, h3 = st.columns([5, 2, 2])
    h1.write("<b>品項名稱</b>", unsafe_allow_html=True)
    h2.write("<div style='text-align:center;'><b>庫存</b></div>", unsafe_allow_html=True)
    h3.write("<div style='text-align:center;'><b>進貨</b></div>", unsafe_allow_html=True)

    with st.form("inventory_form"):
        temp_data = []
        last_item_name = "" 
        for _, row in items.iterrows():
            f_id = str(row['品項ID']).strip(); d_n = str(row['品項名稱']).strip() 
            unit = str(row['單位']).strip(); price = pd.to_numeric(row.get('單價', 0), errors='coerce')
            p_s, p_p = 0.0, 0.0
            if not hist_df.empty:
                past = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['品項ID'].astype(str) == f_id)]
                if not past.empty:
                    latest = past.iloc[-1]; p_s = float(latest.get('本次剩餘', 0)); p_p = float(latest.get('本次叫貨', 0))
            
            c1, c2, c3 = st.columns([5, 2, 2])
            with c1:
                if d_n == last_item_name: st.write(f"<span style='color:gray;'>└ </span> <b>{unit}</b>", unsafe_allow_html=True)
                else: st.write(f"<b>{d_n}</b>", unsafe_allow_html=True)
                last_item_name = d_n
            # 💡 改用 text_input 並配合 label_visibility="collapsed" 以強迫單排
            with c2: t_s_r = st.text_input("", key=f"s_{f_id}", value="0", label_visibility="collapsed")
            with c3: t_p_r = st.text_input("", key=f"p_{f_id}", value="0", label_visibility="collapsed")
            
            try: t_s_v = float(t_s_r) if t_s_r else 0.0
            except: t_s_v = 0.0
            try: t_p_v = float(t_p_r) if t_p_r else 0.0
            except: t_p_v = 0.0
            
            usage = (p_s + p_p) - t_s_v
            temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, f_id, d_n, unit, p_s, p_p, t_s_v, t_p_v, usage, float(price), float(round(t_p_v * price, 1))])

        if st.form_submit_button("💾 儲存盤點結果", use_container_width=True):
            valid = [d for d in temp_data if d[8] > 0 or d[9] > 0]
            sh = get_gspread_client().open_by_key(SHEET_ID)
            ws = sh.worksheet("Records"); ws.append_rows(valid)
            st.success("✅ 儲存成功"); st.session_state.step = "select_vendor"; st.rerun()
    st.button("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"))

# 其他分頁邏輯保持一致 (報表、歷史庫)
elif st.session_state.step == "analysis":
    st.title("📊 進銷存分析")
    a_df = get_worksheet_data("Records")
    # ... (分析報表邏輯)
    st.button("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"))

elif st.session_state.step == "export":
    st.title("📋 今日叫貨明細")
    # ... (叫貨明細邏輯)
    st.button("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"))
