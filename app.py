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
    'item_key': '品項',       # 數據庫唯一鍵（含價格長名）
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
# 2. 強力 CSS 注入 (解決手機排版與按鈕問題)
# =========================
st.set_page_config(page_title="OMS 系統", layout="centered")

st.markdown("""
    <style>
    /* 1. 徹底拔除數字框的 +/- 按鈕與多餘空間 */
    div[data-testid="stNumberInputStepUp"], div[data-testid="stNumberInputStepDown"] {
        display: none !important;
    }
    .stNumberInput input {
        font-size: 16px !important;
        padding: 5px !important;
        text-align: center;
    }
    div[data-testid="stNumberInput"] label { display: none !important; }

    /* 2. 強制橫向佈局 (不論螢幕多窄) */
    [data-testid="column"] {
        flex: 1 1 0% !important;
        min-width: 0px !important;
    }
    div[data-testid="stHorizontalBlock"] > div:nth-child(1) { flex: 2 1 0% !important; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) { flex: 1 1 0% !important; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(3) { flex: 1 1 0% !important; }

    /* 3. 調整字體大小適配手機 */
    p, span, label { font-size: 14px !important; }
    .stMarkdown h3 { font-size: 18px !important; }
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
    st.error("❌ CSV 讀取失敗，請確認標題包含『品項』與『品項名稱』。")
    st.stop()

# 名稱映射表
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
            if st.button(f"📍 {s}", use_container_width=True):
                st.session_state.store = s; st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "select_vendor":
    st.title(f"🏢 {st.session_state.store}")
    st.session_state.record_date = st.date_input("🗓️ 盤點日期", value=st.session_state.record_date)
    v_col = '廠商名稱' if '廠商名稱' in df_i.columns else '廠商'
    vendors = sorted(df_i[v_col].unique())
    for v in vendors:
        if st.button(f"📦 {v}", use_container_width=True):
            st.session_state.vendor = v; st.session_state.history_df = get_cloud_data()
            st.session_state.step = "fill_items"; st.rerun()
    st.write("---")
    if st.button("📄 產生進貨報表", type="primary", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "export"; st.rerun()

elif st.session_state.step == "fill_items":
    st.title(f"📝 {st.session_state.vendor}")
    v_col = '廠商名稱' if '廠商名稱' in df_i.columns else '廠商'
    items = df_i[df_i[v_col] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    # 💡 標題列：左至右
    t1, t2, t3 = st.columns([2, 1, 1])
    t1.write("**品項名稱**")
    t2.write("**庫存**")
    t3.write("**進貨**")
    st.write("---")

    with st.form("inventory_form"):
        temp_data = []
        for _, row in items.iterrows():
            full_name = str(row['品項']).strip()
            display_name = item_display_map.get(full_name, full_name)
            unit = str(row['單位']).strip() if '單位' in row else ""
            price = pd.to_numeric(row.get('單價', 0), errors='coerce')
            
            # 抓取上次數據
            prev_s, prev_p = 0, 0
            if not hist_df.empty:
                past = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['品項'] == full_name)]
                if not past.empty:
                    latest = past.iloc[-1]
                    prev_s = int(pd.to_numeric(latest.get('本次剩餘', 0), errors='coerce') or 0)
                    prev_p = int(pd.to_numeric(latest.get('本次叫貨', 0), errors='coerce') or 0)
            
            # 💡 橫向排版列
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                st.write(f"**{display_name}**")
                st.caption(f"{unit} (上次:{prev_s+prev_p})")
            with c2:
                # 庫存改為數字框
                t_s = st.number_input("庫存", min_value=0, step=1, key=f"s_{full_name}")
            with c3:
                # 進貨改為數字框
                t_p = st.number_input("進貨", min_value=0, step=1, key=f"p_{full_name}")
            
            # 💡 這裡將消耗計算邏輯放入暫存列表
            usage = (prev_s + prev_p) - t_s
            # 存入列表（使用長品項名，確保數據庫連續性）
            temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, full_name, unit, int(prev_s), int(prev_p), int(t_s), int(t_p), int(usage), float(price), float(round(t_p * price, 1))])

        st.write("---")
        if st.form_submit_button("💾 儲存並同步雲端", use_container_width=True):
            if temp_data:
                # 只存有輸入數據的項目
                valid_data = [d for d in temp_data if d[7] > 0 or d[8] > 0]
                if valid_data and sync_to_cloud(pd.DataFrame(valid_data)):
                    st.success("✅ 數據已更新 (期間消耗已結算)"); st.session_state.step = "select_vendor"; st.rerun()
                else: st.warning("請至少填入一項庫存或進貨")
        if st.form_submit_button("❌ 返回", use_container_width=True):
            st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "export":
    st.title("📋 今日進貨明細")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    date_str = str(st.session_state.record_date)
    if not hist_df.empty:
        hist_df['日期'] = hist_df['日期'].astype(str)
        recs = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['日期'] == date_str) & (pd.to_numeric(hist_df['本次叫貨'], errors='coerce') > 0)].copy()
        
        if recs.empty: st.warning("今日無進貨紀錄。")
        else:
            output = f"【{st.session_state.store}】進貨單 ({date_str})\n"
            for v in recs['廠商'].unique():
                output += f"\n{v}\n"
                for _, r in recs[recs['廠商'] == v].iterrows():
                    # 💡 關鍵：報表輸出使用潔淨名稱
                    disp_n = item_display_map.get(r['品項'], r['品項'])
                    u, p, q = r['單位'], int(pd.to_numeric(r['單價'], errors='coerce') or 0), int(pd.to_numeric(r['本次叫貨'], errors='coerce') or 0)
                    output += f"● {disp_n} ( {u} )-${p}：{q}{u}\n"
            st.text_area("📱 LINE 複製格式", value=output, height=300)
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()
