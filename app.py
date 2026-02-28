import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

# =========================
# 1. 戰略參數區 (比例鎖定為 8:1:1)
# =========================
UI_RATIO = [8, 1, 1] 

SHEET_ID = '1c9twPCyOumPKSau5xgUShJJAG-D9aaZBhK2FWBl2zwc' 

COL_MAP = {
    'record_date': '日期',
    'store_name': '店名',
    'vendor_name': '廠商',
    'item_key': '品項',       
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
        # 確保數值轉型，防止分析頁面金額消失
        num_cols = ['本次剩餘', '本次叫貨', '期間消耗', '單價', '總金額']
        for c in num_cols:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
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
# 2. 物理級佈局鎖定 (解決滑動問題 & 移除按鈕)
# =========================
st.set_page_config(page_title="OMS 進銷存系統", layout="centered")

st.markdown(f"""
    <style>
    /* 1. 移除手機版網頁左右多餘邊距，讓表格撐滿 */
    .main .block-container {{
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        padding-top: 1rem !important;
        max-width: 100% !important;
    }}

    /* 2. 徹底隱藏數字框的 +/- 按鈕 */
    button[step="1"], .stNumberInput button,
    div[data-testid="stNumberInputStepUp"], 
    div[data-testid="stNumberInputStepDown"] {{
        display: none !important;
    }}
    
    input[type=number]::-webkit-inner-spin-button, 
    input[type=number]::-webkit-outer-spin-button {{
        -webkit-appearance: none !important;
        margin: 0 !important;
    }}

    /* 3. 強制橫排不換行，且寬度鎖定在螢幕內 (解決滑動問題) */
    [data-testid="stHorizontalBlock"] {{
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        width: 100% !important;
        overflow: hidden !important;
    }}
    
    [data-testid="column"] {{
        min-width: 0px !important;
        flex: 1 1 auto !important;
    }}

    /* 物理比例控制：8:1:1 */
    div[data-testid="stHorizontalBlock"] > div:nth-child(1) {{ flex: {UI_RATIO[0]} !important; }}
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) {{ flex: {UI_RATIO[1]} !important; }}
    div[data-testid="stHorizontalBlock"] > div:nth-child(3) {{ flex: {UI_RATIO[2]} !important; }}

    /* 4. 輸入框視覺縮小與字體對齊 */
    div[data-testid="stNumberInput"] label {{ display: none !important; }}
    .stNumberInput input {{
        font-size: 14px !important;
        padding: 4px !important;
        text-align: center;
    }}
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
if df_i is None: st.error("❌ 檔案讀取失敗"); st.stop()

item_display_map = df_i.set_index('品項')['品項名稱'].to_dict()

if "step" not in st.session_state: st.session_state.step = "select_store"
if "record_date" not in st.session_state: st.session_state.record_date = date.today()

# =========================
# 3. 執行介面
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
    if st.button("📄 產生今日進貨明細", type="primary", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "export"; st.rerun()
    if st.button("📊 期間進銷存分析", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "analysis"; st.rerun()
    if st.button("⬅️ 返回分店列表", use_container_width=True):
        st.session_state.step = "select_store"; st.rerun()

elif st.session_state.step == "fill_items":
    st.title(f"📝 {st.session_state.vendor}")
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    # 標題列
    h1, h2, h3 = st.columns(UI_RATIO)
    h1.caption("**品項**")
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
            
            p_s, p_p = 0, 0
            if not hist_df.empty:
                past = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['品項'] == f_n)]
                if not past.empty:
                    latest = past.iloc[-1]
                    p_s = int(pd.to_numeric(latest.get('本次剩餘', 0), errors='coerce') or 0)
                    p_p = int(pd.to_numeric(latest.get('本次叫貨', 0), errors='coerce') or 0)
            
            # 💡 強制 8:1:1 橫向排版
            c1, c2, c3 = st.columns(UI_RATIO)
            with c1:
                st.markdown(f"**{d_n}**")
                st.caption(f"{unit} (前:{p_s+p_p})")
            with c2:
                t_s = st.number_input("庫", min_value=0, step=1, key=f"s_{f_n}")
            with c3:
                t_p = st.number_input("進", min_value=0, step=1, key=f"p_{f_n}")
            
            usage = (p_s + p_p) - t_s
            temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, f_n, d_n, unit, int(p_s), int(p_p), int(t_s), int(t_p), int(usage), float(price), float(round(t_p * price, 1))])

        if st.form_submit_button("💾 儲存並同步", use_container_width=True):
            valid = [d for d in temp_data if d[8] > 0 or d[9] > 0]
            if valid and sync_to_cloud(pd.DataFrame(valid)):
                st.success("✅ 儲存成功"); st.session_state.step = "select_vendor"; st.rerun()
    
    if st.button("⬅️ 返回廠商列表", use_container_width=True):
        st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "export":
    st.title("📋 今日進貨報表")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    date_str = str(st.session_state.record_date)
    if not hist_df.empty:
        hist_df['日期'] = hist_df['日期'].astype(str)
        recs = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['日期'] == date_str) & (pd.to_numeric(hist_df['本次叫貨'], errors='coerce') > 0)].copy()
        
        if recs.empty: st.warning("今日無進貨紀錄")
        else:
            output = f"【{st.session_state.store}】進貨單 ({date_str})\n"
            for v in recs['廠商'].unique():
                output += f"\n{v}\n"
                for _, r in recs[recs['廠商'] == v].iterrows():
                    d_n = r.get('品項名稱', item_display_map.get(r['品項'], r['品項']))
                    u, q = r['單位'], int(r['本次叫貨'])
                    output += f"● {d_n}：{q}{u}\n"
            st.text_area("📱 LINE 複製格式", value=output, height=300)
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "analysis":
    st.title("📊 期間分析 (含成本金額)")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    c1, c2 = st.columns(2)
    start, end = c1.date_input("起始", value=date.today()-timedelta(7)), c2.date_input("結束", value=date.today())
    if not hist_df.empty:
        hist_df['日期'] = pd.to_datetime(hist_df['日期']).dt.date
        analysis = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['日期'] >= start) & (hist_df['日期'] <= end)].copy()
        if not analysis.empty:
            summary = analysis.groupby(['廠商', '品項', '單位', '單價']).agg({'期間消耗': 'sum', '本次叫貨': 'sum', '總金額': 'sum'}).reset_index()
            summary['品項名稱'] = summary['品項'].map(lambda x: item_display_map.get(x, x))
            last_recs = analysis.sort_values('日期').groupby('品項').tail(1)
            stock_map = last_recs.set_index('品項')['本次剩餘'].to_dict()
            summary['目前庫存'] = summary['品項'].map(stock_map).fillna(0).astype(int)
            summary['庫存金額'] = summary['目前庫存'] * summary['單價']
            st.dataframe(summary[['廠商', '品項名稱', '單位', '單價', '期間消耗', '本次叫貨', '總金額', '目前庫存', '庫存金額']], use_container_width=True)
            m1, m2 = st.columns(2)
            m1.metric("採購總金額", f"${summary['總金額'].sum():,.0f}")
            m2.metric("剩餘庫存總值", f"${summary['庫存金額'].sum():,.0f}")
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()
