import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

# =========================
# 1. 核心設定 (Records 欄位對照)
# =========================
SHEET_ID = '1c9twPCyOumPKSau5xgUShJJAG-D9aaZBhK2FWBl2zwc' 

COL_MAP = {
    'record_date': '日期',
    'store_name': '店名',
    'vendor_name': '廠商',
    'item_key': '品項',       # 數據庫存儲長名 (含價格)
    'item_display': '品項名稱', # 顯示用短名
    'unit': '單位',
    'last_stock': '上次剩餘',
    'last_purchase': '上次叫貨',
    'this_stock': '庫存',
    'this_purchase': '進貨',
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
# 2. 強力佈局控制 (CSS 控制)
# =========================
st.set_page_config(page_title="OMS 進銷存", layout="centered")

st.markdown("""
    <style>
    /* 1. 強制拔除數字輸入框的 + / - 按鈕 */
    button[step="1"], .stNumberInput button { display: none !important; }
    div[data-testid="stNumberInputStepUp"], div[data-testid="stNumberInputStepDown"] {
        display: none !important;
    }
    input[type=number] { -moz-appearance: textfield; }
    input[type=number]::-webkit-inner-spin-button, input[type=number]::-webkit-outer-spin-button {
        -webkit-appearance: none; margin: 0;
    }

    /* 2. 手機版強制橫向排版 (比例 2:1:1) */
    [data-testid="column"] {
        flex: 1 1 0% !important;
        min-width: 0px !important;
    }
    div[data-testid="stHorizontalBlock"] > div:nth-child(1) { flex: 2 1 0% !important; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) { flex: 1 1 0% !important; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(3) { flex: 1 1 0% !important; }

    /* 3. 移除標籤與縮小間距 */
    div[data-testid="stNumberInput"] label { display: none !important; }
    .stNumberInput { padding-top: 0px !important; }
    .stMarkdown p { font-size: 14px !important; margin-bottom: 0px !important; }
    </style>
    """, unsafe_allow_html=True)

CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv")
CSV_STORE = Path("品項總覽.xlsx - 分店.csv")

def load_csv_safe(path):
    for enc in ['utf-8-sig', 'utf-8', 'cp950', 'big5']:
        try:
            df = pd.read_csv(path, encoding=enc)
            df.columns = [str(c).strip() for c in df.columns]
            return df.map(lambda x: str(x).strip() if isinstance(x, str) else x)
        except: continue
    return None

df_s, df_i = load_csv_safe(CSV_STORE), load_csv_safe(CSV_ITEMS)
if df_i is None or '品項' not in df_i.columns:
    st.error("❌ CSV 欄位讀取異常，請確認包含「品項」與「品項名稱」"); st.stop()

# 名稱映射表
item_display_map = df_i.set_index('品項')['品項名稱'].to_dict()

if "step" not in st.session_state: st.session_state.step = "select_store"
if "record_date" not in st.session_state: st.session_state.record_date = date.today()

# =========================
# 3. 執行流程
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
    st.session_state.record_date = st.date_input("🗓️ 日期", value=st.session_state.record_date)
    v_col = '廠商名稱' if '廠商名稱' in df_i.columns else '廠商'
    vendors = sorted(df_i[v_col].unique())
    for v in vendors:
        if st.button(f"📦 {v}", key=f"v_{v}", use_container_width=True):
            st.session_state.vendor = v; st.session_state.history_df = get_cloud_data()
            st.session_state.step = "fill_items"; st.rerun()
    st.write("---")
    if st.button("📄 產生今日進貨報表", type="primary", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "export"; st.rerun()
    if st.button("⬅️ 返回分店列表", use_container_width=True):
        st.session_state.step = "select_store"; st.rerun()

elif st.session_state.step == "fill_items":
    st.title(f"📝 {st.session_state.vendor}")
    v_col = '廠商名稱' if '廠商名稱' in df_i.columns else '廠商'
    items = df_i[df_i[v_col] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    # 💡 標題與消耗量資訊
    h1, h2, h3 = st.columns([2, 1, 1])
    h1.caption("**品項名稱**")
    h2.caption("**庫存**")
    h3.caption("**進貨**")
    st.write("---")

    with st.form("inventory_form"):
        temp_data = []
        for _, row in items.iterrows():
            f_n = str(row['品項']).strip()
            d_n = item_display_map.get(f_n, f_n)
            unit = str(row['單位']).strip() if '單位' in row else ""
            price = pd.to_numeric(row.get('單價', 0), errors='coerce')
            
            # 歷史庫存
            p_s, p_p = 0, 0
            if not hist_df.empty:
                past = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['品項'] == f_n)]
                if not past.empty:
                    latest = past.iloc[-1]
                    p_s = int(pd.to_numeric(latest.get('本次剩餘', 0), errors='coerce') or 0)
                    p_p = int(pd.to_numeric(latest.get('本次叫貨', 0), errors='coerce') or 0)
            
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                st.markdown(f"**{d_n}**")
                # 💡 期間消耗入口顯示
                st.caption(f"{unit} (前結:{p_s+p_p})")
            with c2:
                t_s = st.number_input("庫", min_value=0, step=1, key=f"s_{f_n}")
            with c3:
                t_p = st.number_input("進", min_value=0, step=1, key=f"p_{f_n}")
            
            # 計算消耗量並暫存
            usage = (p_s + p_p) - t_s
            temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, f_n, d_n, unit, int(p_s), int(p_p), int(t_s), int(t_p), int(usage), float(price), float(round(t_p * price, 1))])

        st.write("---")
        if st.form_submit_button("💾 儲存並計算消耗", use_container_width=True):
            valid = [d for d in temp_data if d[8] > 0 or d[9] > 0]
            if valid and sync_to_cloud(pd.DataFrame(valid)):
                st.success("✅ 儲存成功 (消耗已結算)"); st.session_state.step = "select_vendor"; st.rerun()
            else: st.warning("請輸入數值")
            
    if st.button("⬅️ 放棄並返回廠商", use_container_width=True):
        st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "export":
    st.title("📋 今日進貨報表")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    date_str = str(st.session_state.record_date)
    if not hist_df.empty:
        hist_df['日期'] = hist_df['日期'].astype(str)
        recs = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['日期'] == date_str) & (pd.to_numeric(hist_df['本次叫貨'], errors='coerce') > 0)].copy()
        
        if recs.empty: st.warning("今日尚無進貨紀錄。")
        else:
            # 💡 明細格式：● 品項名稱-$單價：進貨量單位
            output = f"{date_str}\n{st.session_state.store}\n"
            for v in recs['廠商'].unique():
                output += f"\n{v}\n"
                for _, r in recs[recs['廠商'] == v].iterrows():
                    d_n = r.get('品項名稱', item_display_map.get(r['品項'], r['品項']))
                    u, p, q = r['單位'], int(pd.to_numeric(r['單價'], errors='coerce') or 0), int(pd.to_numeric(r['本次叫貨'], errors='coerce') or 0)
                    output += f"● {d_n}-${p}：{q}{u}\n"
            st.text_area("📱 LINE 複製格式", value=output, height=300)
    
    if st.button("⬅️ 返回廠商列表", use_container_width=True):
        st.session_state.step = "select_vendor"; st.rerun()
