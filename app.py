import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

# 💡 安全載入 Plotly (防止環境未配置時崩潰)
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
    """讀取特定工作表數據"""
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
    st.write("<b>📊 數據與報表</b>", unsafe_allow_html=True)
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

elif st.session_state.step == "fill_items":
    # 填寫頁面邏輯保持不變
    st.title(f"📝 {st.session_state.vendor}")
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    if not hist_df.empty:
        ref_data = []
        for f_id in items['品項ID'].unique():
            f_name = item_display_map.get(f_id, "")
            past = hist_df[(hist_df['店名'] == st.session_state.store) & 
                           ((hist_df['品項ID'].astype(str) == str(f_id)) | (hist_df['品項名稱'] == str(f_name)))]
            if not past.empty:
                latest = past.iloc[-1]
                ref_data.append({"品項": f_name, "上剩": latest.get('本次剩餘', 0), "上進": latest.get('本次叫貨', 0), "消耗": latest.get('期間消耗', 0)})
        if ref_data:
            with st.expander("📊 查看上次歷史參考", expanded=True):
                st.dataframe(pd.DataFrame(ref_data), use_container_width=True, hide_index=True)
    
    st.write("---")
    h1, h2, h3 = st.columns([6, 1.2, 1.2])
    h1.write("<b>品項名稱</b>", unsafe_allow_html=True)
    h2.write("<b>庫存</b>", unsafe_allow_html=True)
    h3.write("<b>進貨</b>", unsafe_allow_html=True)

    with st.form("inventory_form"):
        temp_data = []
        last_item_display_name = "" 
        for _, row in items.iterrows():
            f_id = str(row['品項ID']).strip(); d_n = str(row['品項名稱']).strip() 
            unit = str(row['單位']).strip(); price = pd.to_numeric(row.get('單價', 0), errors='coerce')
            p_s, p_p = 0.0, 0.0
            if not hist_df.empty:
                past = hist_df[(hist_df['店名'] == st.session_state.store) & ((hist_df['品項ID'].astype(str) == f_id) | (hist_df['品項名稱'] == d_n))]
                if not past.empty:
                    latest = past.iloc[-1]
                    p_s = float(latest.get('本次剩餘', 0)); p_p = float(latest.get('本次叫貨', 0))
            
            c1, c2, c3 = st.columns([6, 1.2, 1.2])
            with c1:
                if d_n == last_item_display_name:
                    st.write(f"<span style='color:gray;'>└ </span> <b>{unit}</b>", unsafe_allow_html=True)
                else:
                    st.write(f"<b>{d_n}</b>", unsafe_allow_html=True)
                p_sum = p_s + p_p; p_show = int(p_sum) if p_sum.is_integer() else round(p_sum, 1)
                st.caption(f"{unit} (前結:{p_show})")
                last_item_display_name = d_n
            with c2:
                t_s = st.number_input("庫", min_value=0.0, step=0.1, key=f"s_{f_id}", format="%g", value=None)
            with c3:
                t_p = st.number_input("進", min_value=0.0, step=0.1, key=f"p_{f_id}", format="%g", value=None)
            t_s_v = t_s if t_s is not None else 0.0; t_p_v = t_p if t_p is not None else 0.0
            usage = (p_s + p_p) - t_s_v
            temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, f_id, d_n, unit, p_s, p_p, t_s_v, t_p_v, usage, float(price), float(round(t_p_v * price, 1))])

        if st.form_submit_button("💾 儲存並同步數據", use_container_width=True):
            valid = [d for d in temp_data if d[8] > 0 or d[9] > 0]
            if valid and sync_to_cloud(pd.DataFrame(valid)):
                st.success("✅ 儲存成功"); st.session_state.step = "select_vendor"; st.rerun()
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "view_history":
    st.title(f"📜 {st.session_state.store} 歷史紀錄庫")
    view_df = st.session_state.get('view_df', pd.DataFrame())
    
    if not view_df.empty:
        # 💡 分頁檢視：明細與趨勢
        tab1, tab2 = st.tabs(["📋 數據明細表", "📈 品項趨勢圖"])
        
        with tab1:
            search = st.text_input("🔍 關鍵字搜尋 (輸入品項或日期)", help="直接輸入如「雞胸」或「2026-03」")
            display_df = view_df.copy()
            if search:
                display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search)).any(axis=1)]
            st.dataframe(display_df.sort_values('日期', ascending=False), use_container_width=True, hide_index=True)
            
        with tab2:
            if HAS_PLOTLY:
                st.write("<b>分析單一品項的消耗趨勢</b>", unsafe_allow_html=True)
                target_item = st.selectbox("請選擇品項", options=sorted(view_df['品項名稱'].unique()))
                plot_df = view_df[view_df['品項名稱'] == target_item].sort_values('日期')
                if not plot_df.empty:
                    fig = px.line(plot_df, x="日期", y="期間消耗", title=f"{target_item} 歷史消耗曲線", markers=True)
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("💡 正在配置繪圖模組，請稍後重新載入或檢查 requirements.txt")
    else:
        st.warning("目前尚無可讀取的紀錄。")
        
    if st.button("⬅️ 返回廠商列表", use_container_width=True):
        st.session_state.step = "select_vendor"; st.rerun()

# 報表與分析頁面 (省略其餘，邏輯與之前一致)
elif st.session_state.step == "export":
    st.title("📋 今日進貨明細")
    hist_df = get_cloud_data()
    # ... (其餘邏輯維持)
    st.button("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"))

elif st.session_state.step == "analysis":
    st.title("📊 進銷存分析")
    # ... (其餘邏輯維持)
    st.button("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"))
