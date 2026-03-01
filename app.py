import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

# 💡 安全載入 Plotly
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
    try:
        client = get_gspread_client()
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        num_cols = ['上次剩餘', '上次叫貨', '本次剩餘', '本次叫貨', '期間消耗', '單價', '總金額']
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

def get_cloud_data():
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
# 2. 全域視覺標準 (強力修復重疊問題)
# =========================
st.set_page_config(page_title="OMS 系統", layout="centered")
st.markdown("""
    <style>
    /* 1. 強制重磅字體 */
    html, body, [class*="css"], .stMarkdown, p, span, div, b {
        font-family: 'PingFang TC', 'Microsoft JhengHei', sans-serif !important;
        font-weight: 700 !important;
    }
    
    /* 2. 徹底消滅所有輸入框內的英文字、箭頭、微調組件 (解決 arr_right/down 重疊) */
    input::-webkit-outer-spin-button,
    input::-webkit-inner-spin-button {
        -webkit-appearance: none !important;
        margin: 0 !important;
    }
    input[type=number] {
        -moz-appearance: textfield !important;
        appearance: none !important;
    }
    
    /* 隱藏 Streamlit 預設的數字輸入框標籤，防止與自定義標題重疊 */
    div[data-testid="stNumberInput"] label {
        display: none !important;
    }

    /* 鎖定輸入框樣式 */
    .stNumberInput input { 
        font-weight: 800 !important; 
        font-size: 16px !important; 
        text-align: center !important; 
        background-color: rgba(255, 255, 255, 0.05) !important;
    }

    /* 物理間距 */
    .spacer { margin: 25px 0px; border-top: 1px solid #444; }
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
    
    st.write("<b>📦 請選擇廠商</b>", unsafe_allow_html=True)
    if df_i is not None:
        vendors = sorted(df_i['廠商名稱'].unique())
        v_cols = st.columns(2)
        for i, v in enumerate(vendors):
            with v_cols[i % 2]:
                if st.button(v, key=f"v_{v}", use_container_width=True):
                    st.session_state.vendor = v; st.session_state.history_df = get_cloud_data()
                    st.session_state.step = "fill_items"; st.rerun()
    
    st.markdown('<div class="spacer"></div>', unsafe_allow_html=True)
    
    with st.container():
        st.write("<b>🛠️ 系統功能</b>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📄 產生明細", type="primary", use_container_width=True):
                st.session_state.history_df = get_cloud_data(); st.session_state.step = "export"; st.rerun()
        with c2:
            if st.button("📈 進銷存分析", use_container_width=True):
                st.session_state.history_df = get_cloud_data(); st.session_state.step = "analysis"; st.rerun()
        
        history_sheet = f"{st.session_state.store}_紀錄"
        if st.button(f"📜 查看 {st.session_state.store} 紀錄庫", use_container_width=True):
            st.session_state.view_df = get_worksheet_data(history_sheet)
            st.session_state.step = "view_history"; st.rerun()
            
    if st.button("⬅️ 返回分店列表", use_container_width=True):
        st.session_state.step = "select_store"; st.rerun()

elif st.session_state.step == "fill_items":
    if "vendor" not in st.session_state: st.session_state.step = "select_vendor"; st.rerun()
    st.markdown("<style>.block-container { padding-left: 0.3rem !important; padding-right: 0.3rem !important; }</style>", unsafe_allow_html=True)
    st.title(f"📝 {st.session_state.vendor}")
    
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    st.write("---")
    # 💡 標題欄位分配 (加大間距防止重疊)
    h1, h2, h3 = st.columns([5, 1.5, 1.5])
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
                    latest = past.iloc[-1]
                    p_s = float(latest.get('本次剩餘', 0)); p_p = float(latest.get('本次叫貨', 0))
            
            c1, c2, c3 = st.columns([5, 1.5, 1.5])
            with c1:
                if d_n == last_item_name: st.write(f"<span style='color:gray;'>└ </span> <b>{unit}</b>", unsafe_allow_html=True)
                else: st.write(f"<b>{d_n}</b>", unsafe_allow_html=True)
                st.caption(f"{unit} (前結:{int(p_s+p_p)})")
                last_item_name = d_n
            with c2: t_s = st.number_input("庫", min_value=0.0, step=0.1, key=f"s_{f_id}", format="%g", value=None)
            with c3: t_p = st.number_input("進", min_value=0.0, step=0.1, key=f"p_{f_id}", format="%g", value=None)
            t_s_v = t_s if t_s is not None else 0.0; t_p_v = t_p if t_p is not None else 0.0
            usage = (p_s + p_p) - t_s_v
            temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, f_id, d_n, unit, p_s, p_p, t_s_v, t_p_v, usage, float(price), float(round(t_p_v * price, 1))])

        if st.form_submit_button("💾 儲存盤點數據", use_container_width=True):
            valid = [d for d in temp_data if d[8] > 0 or d[9] > 0]
            if valid and sync_to_cloud(pd.DataFrame(valid)):
                st.success("✅ 儲存成功"); st.session_state.step = "select_vendor"; st.rerun()
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "analysis":
    st.title("📊 進銷存分析")
    hist_df = get_cloud_data()
    start = st.date_input("開始", value=date.today()-timedelta(7)); end = st.date_input("結束", value=date.today())
    
    if not hist_df.empty:
        hist_df['日期'] = pd.to_datetime(hist_df['日期']).dt.date
        analysis = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['日期'] >= start) & (hist_df['日期'] <= end)]
        if not analysis.empty:
            summary = analysis.groupby(['廠商', '品項名稱', '單位', '單價']).agg({'期間消耗': 'sum', '本次叫貨': 'sum', '總金額': 'sum'}).reset_index()
            # 💡 核心修正：計算庫存金額
            last_recs = analysis.sort_values('日期').groupby('品項名稱').tail(1)
            stock_map = last_recs.set_index('品項名稱')['本次剩餘'].to_dict()
            summary['期末庫存'] = summary['品項名稱'].map(stock_map).fillna(0)
            summary['庫存金額'] = summary['期末庫存'] * summary['單價']
            
            buy_total = summary['總金額'].sum()
            inv_total = summary['庫存金額'].sum()
            
            st.markdown(f"#### 💰 採購總額：${buy_total:,.1f} | 📦 庫存總值：${inv_total:,.1f}")
            st.dataframe(summary[['廠商', '品項名稱', '單位', '期間消耗', '本次叫貨', '總金額', '期末庫存', '庫存金額']], use_container_width=True, hide_index=True)
        else: st.info("選定期間內無數據。")
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "view_history":
    st.title(f"📜 {st.session_state.store} 紀錄庫")
    view_df = st.session_state.get('view_df', pd.DataFrame())
    if not view_df.empty:
        s = st.text_input("🔍 關鍵字搜尋")
        d_df = view_df.copy()
        if s: d_df = d_df[d_df.astype(str).apply(lambda x: x.str.contains(s)).any(axis=1)]
        st.dataframe(d_df.sort_values('日期', ascending=False), use_container_width=True, hide_index=True)
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "export":
    st.title("📋 今日叫貨明細")
    h_df = get_cloud_data()
    week_map = {0:'一', 1:'二', 2:'三', 3:'四', 4:'五', 5:'六', 6:'日'}
    deliv_date = st.session_state.record_date + timedelta(days=1)
    header = f"{deliv_date.month}/{deliv_date.day}({week_map[deliv_date.weekday()]})"
    if not h_df.empty:
        recs = h_df[(h_df['店名'] == st.session_state.store) & (h_df['日期'].astype(str) == str(st.session_state.record_date)) & (h_df['本次叫貨'] > 0)]
        if not recs.empty:
            out = f"{header}\n"
            for v in recs['廠商'].unique():
                out += f"\n{v}\n{st.session_state.store}\n"
                for _, r in recs[recs['廠商'] == v].iterrows():
                    val = float(r['本次叫貨']); v_s = int(val) if val.is_integer() else val
                    out += f"{r['品項名稱']} {v_s} {r['單位']}\n"
                out += f"禮拜{week_map[deliv_date.weekday()]}到，謝謝\n"
            st.text_area("LINE 複製", value=out, height=300)
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()
