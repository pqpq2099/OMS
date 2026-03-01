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
# 2. 全域視覺標準 (強力鎖定單排與去噪)
# =========================
st.set_page_config(page_title="OMS 系統", layout="centered")
st.markdown("""
    <style>
    /* 1. 字體重量鎖定 */
    html, body, [class*="css"], .stMarkdown, p, span, div, b {
        font-family: 'PingFang TC', 'Microsoft JhengHei', sans-serif !important;
        font-weight: 700 !important;
    }
    
    /* 2. 徹底消滅 +- 按鈕與 arr_down 重疊亂碼 */
    div[data-testid="stNumberInput"] label,
    [aria-label^="arr_"], [aria-label^="val_"],
    div[data-testid="stNumberInputStepUp"], 
    div[data-testid="stNumberInputStepDown"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
        font-size: 0px !important;
    }

    /* 3. 物理性鎖定單排：縮減輸入框寬度並對齊 */
    .stNumberInput input {
        font-weight: 800 !important;
        font-size: 16px !important;
        text-align: center !important;
        padding: 4px !important;
        height: 40px !important;
        margin: 0 !important;
    }
    
    /* 4. 手機端強制雙欄廠商列表 */
    div:has(div > button[key^="v_"]) {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 8px !important;
    }
    div:has(> button[key^="v_"]) {
        flex: 1 1 calc(50% - 8px) !important;
        min-width: 120px !important;
    }

    /* 5. 標題與表格物理間距微調 */
    .stHorizontalBlock { gap: 0.1rem !important; align-items: center !important; }
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
    # 💡 簡約標題：移除多餘描述
    st.write("<b>📦 廠商</b>", unsafe_allow_html=True)
    
    if df_i is not None:
        vendors = sorted(df_i['廠商名稱'].unique())
        # 使用 CSS 強制雙欄
        for v in vendors:
            if st.button(v, key=f"v_{v}", use_container_width=True):
                st.session_state.vendor = v; st.session_state.history_df = get_worksheet_data("Records")
                st.session_state.step = "fill_items"; st.rerun()
    
    st.write("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📄 產生明細", type="primary", use_container_width=True):
            st.session_state.history_df = get_worksheet_data("Records"); st.session_state.step = "export"; st.rerun()
    with c2:
        if st.button("📈 進銷存分析", use_container_width=True):
            st.session_state.history_df = get_worksheet_data("Records"); st.session_state.step = "analysis"; st.rerun()
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_store"; st.rerun()

elif st.session_state.step == "fill_items":
    if "vendor" not in st.session_state: st.session_state.step = "select_vendor"; st.rerun()
    st.markdown("<style>.block-container { padding-left: 0.1rem !important; padding-right: 0.1rem !important; }</style>", unsafe_allow_html=True)
    st.title(f"📝 {st.session_state.vendor}")
    
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    # 標題列：強制對齊比例
    h1, h2, h3 = st.columns([4, 2, 2])
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
                past = hist_df[(hist_df['店名'] == st.session_state.store) & ((hist_df['品項ID'].astype(str) == f_id) | (hist_df['品項名稱'] == d_n))]
                if not past.empty:
                    latest = past.iloc[-1]; p_s = float(latest.get('本次剩餘', 0)); p_p = float(latest.get('本次叫貨', 0))
            
            c1, c2, c3 = st.columns([4, 2, 2])
            with c1:
                if d_n == last_item_name: st.write(f"<span style='color:gray;'>└ </span> <b>{unit}</b>", unsafe_allow_html=True)
                else: st.write(f"<b>{d_n}</b>", unsafe_allow_html=True)
                last_item_name = d_n
            # 💡 物理隱藏 label，徹底消滅重疊亂碼與 +- 按鈕
            with c2: t_s = st.number_input("", key=f"s_{f_id}", min_value=0.0, step=0.1, format="%g", value=0.0, label_visibility="collapsed")
            with c3: t_p = st.number_input("", key=f"p_{f_id}", min_value=0.0, step=0.1, format="%g", value=0.0, label_visibility="collapsed")
            
            t_s_v = t_s if t_s is not None else 0.0; t_p_v = t_p if t_p is not None else 0.0
            usage = (p_s + p_p) - t_s_v
            temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, f_id, d_n, unit, p_s, p_p, t_s_v, t_p_v, usage, float(price), float(round(t_p_v * price, 1))])

        if st.form_submit_button("💾 儲存盤點結果", use_container_width=True):
            valid = [d for d in temp_data if d[8] > 0 or d[9] > 0]
            sh = get_gspread_client().open_by_key(SHEET_ID)
            ws = sh.worksheet("Records"); ws.append_rows(valid)
            st.success("✅ 儲存成功"); st.session_state.step = "select_vendor"; st.rerun()
    st.button("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"))
