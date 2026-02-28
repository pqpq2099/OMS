import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

# =========================
# 1. 核心與雲端設定
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
        st.error(f"⚠️ 金鑰錯誤: {e}"); return None

def get_cloud_data():
    try:
        client = get_gspread_client()
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet("Records")
        df = pd.DataFrame(ws.get_all_records())
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
# 2. 佈局樣式控制 (針對輸入分頁深度窄化)
# =========================
st.set_page_config(page_title="OMS 系統", layout="centered")

st.markdown("""
    <style>
    /* 1. 全域窄版優化 */
    .block-container {
        padding-left: 0.3rem !important;
        padding-right: 0.3rem !important;
        max-width: 100% !important;
    }

    /* 2. 徹底拔除數字加減按鈕 */
    div[data-testid="stNumberInputStepUp"], 
    div[data-testid="stNumberInputStepDown"],
    .stNumberInput button {
        display: none !important;
    }
    input[type=number] {
        -moz-appearance: textfield !important;
        -webkit-appearance: none !important;
        margin: 0 !important;
    }

    /* 3. 輸入欄位橫排：極致窄化鎖定 (庫/進 52px) */
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
    }
    /* 第一欄：品項名稱 (自動伸展) */
    div[data-testid="stHorizontalBlock"] > div:nth-child(1) {
        flex: 1 1 auto !important;
        min-width: 0px !important;
    }
    /* 第二、三欄：庫存與進貨 (強力鎖死窄度) */
    div[data-testid="stHorizontalBlock"] > div:nth-child(2),
    div[data-testid="stHorizontalBlock"] > div:nth-child(3) {
        flex: 0 0 52px !important;
        min-width: 52px !important;
        max-width: 52px !important;
    }

    /* 4. 輸入框視覺優化：隱藏 Label，文字置中 */
    div[data-testid="stNumberInput"] label { display: none !important; }
    .stNumberInput input {
        font-size: 14px !important;
        padding: 4px 2px !important;
        text-align: center !important;
    }
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
    if st.button("📄 產生今日進貨報表", type="primary", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "export"; st.rerun()
    if st.button("📊 期間進銷存分析", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "analysis"; st.rerun()
    if st.button("⬅️ 返回分店列表", use_container_width=True):
        st.session_state.step = "select_store"; st.rerun()

elif st.session_state.step == "fill_items":
    st.title(f"📝 {st.session_state.vendor}")
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    # 標題列：比例需與下方內容嚴格對齊
    h1, h2, h3 = st.columns([6, 1, 1])
    h1.caption("**品項**")
    h2.caption("**庫**")
    h3.caption("**進**")
    st.write("---")

    with st.form("inventory_form"):
        temp_data = []
        for _, row in items.iterrows():
            f_n = str(row['品項']).strip()
            d_n = item_display_map.get(f_n, f_n)
            unit = str(row['單位']).strip() if '單位' in row else ""
            price = pd.to_numeric(row.get('單價', 0), errors='coerce')
            
            p_s, p_p = 0.0, 0.0
            if not hist_df.empty:
                past = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['品項'] == f_n)]
                if not past.empty:
                    latest = past.iloc[-1]
                    p_s = float(latest.get('本次剩餘', 0))
                    p_p = float(latest.get('本次叫貨', 0))
            
            c1, c2, c3 = st.columns([6, 1, 1])
            with c1:
                st.markdown(f"**{d_n}**")
                p_sum = p_s + p_p
                # 歷史顯示智慧去零
                p_show = int(p_sum) if p_sum.is_integer() else round(p_sum, 1)
                st.caption(f"{unit} (前:{p_show})")
            with c2:
                # 💡 關鍵：format="%g" 確保不顯示 .00，value=None 確保預設空白不主動顯示數字
                t_s = st.number_input("庫", min_value=0.0, step=0.1, key=f"s_{f_n}", format="%g", value=None)
            with c3:
                t_p = st.number_input("進", min_value=0.0, step=0.1, key=f"p_{f_n}", format="%g", value=None)
            
            t_s_v = t_s if t_s is not None else 0.0
            t_p_v = t_p if t_p is not None else 0.0
            usage = (p_s + p_p) - t_s_v
            temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, f_n, d_n, unit, p_s, p_p, t_s_v, t_p_v, usage, float(price), float(round(t_p_v * price, 1))])

        if st.form_submit_button("💾 儲存並同步", use_container_width=True):
            valid = [d for d in temp_data if d[8] > 0 or d[9] > 0]
            if valid and sync_to_cloud(pd.DataFrame(valid)):
                st.success("✅ 儲存成功"); st.session_state.step = "select_vendor"; st.rerun()
    
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()

# (其餘頁面 export/analysis 邏輯維持不變...)
elif st.session_state.step == "export":
    st.title("📋 今日進貨報表")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    date_str = str(st.session_state.record_date)
    if not hist_df.empty:
        hist_df['日期'] = hist_df['日期'].astype(str)
        recs = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['日期'] == date_str) & (hist_df['本次叫貨'] > 0)].copy()
        if not recs.empty:
            output = f"【{st.session_state.store}】進貨單 ({date_str})\n"
            for v in recs['廠商'].unique():
                output += f"\n{v}\n"
                for _, r in recs[recs['廠商'] == v].iterrows():
                    d_n = r.get('品項名稱', item_display_map.get(r['品項'], r['品項']))
                    val = float(r['本次叫貨'])
                    val_s = int(val) if val.is_integer() else val
                    output += f"● {d_n}：{val_s}{r['單位']}\n"
            st.text_area("📱 LINE 複製", value=output, height=300)
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "analysis":
    st.title("📊 期間分析")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    start = st.date_input("起始", value=date.today()-timedelta(7))
    end = st.date_input("結束", value=date.today())
    if not hist_df.empty:
        hist_df['日期'] = pd.to_datetime(hist_df['日期']).dt.date
        analysis = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['日期'] >= start) & (hist_df['日期'] <= end)].copy()
        if not analysis.empty:
            summary = analysis.groupby(['廠商', '品項', '單位', '單價']).agg({'期間消耗': 'sum', '本次叫貨': 'sum', '總金額': 'sum'}).reset_index()
            summary['品項名稱'] = summary['品項'].map(lambda x: item_display_map.get(x, x))
            for c in ['期間消耗', '本次叫貨']:
                summary[c] = summary[c].apply(lambda x: int(x) if x == int(x) else round(x, 1))
            st.markdown(f"**採購支出：** ${summary['總金額'].sum():,.1f}")
            st.dataframe(summary[['廠商', '品項名稱', '期間消耗', '本次叫貨', '總金額']], use_container_width=True)
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()
