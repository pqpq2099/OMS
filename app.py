import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

# =========================
# 1. 核心設定 (請確認 Google 試算表標題包含「品項」)
# =========================
SHEET_ID = '1c9twPCyOumPKSau5xgUShJJAG-D9aaZBhK2FWBl2zwc' 

COL_MAP = {
    'record_date': '日期',
    'store_name': '店名',
    'vendor_name': '廠商',
    'item_name': '品項',      # 數據比對用完整長名
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
        st.error(f"⚠️ 金鑰讀取失敗: {e}"); return None

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
# 2. 檔案載入與樣式硬核注入
# =========================
CSV_STORE = Path("品項總覽.xlsx - 分店.csv")
CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv")

def load_csv_safe(path):
    for enc in ['utf-8-sig', 'utf-8', 'cp950', 'big5']:
        try:
            df = pd.read_csv(path, encoding=enc)
            df.columns = [str(c).strip().replace('\ufeff', '') for c in df.columns]
            return df.map(lambda x: str(x).strip() if isinstance(x, str) else x)
        except: continue
    return None

st.set_page_config(page_title="OMS 進銷存系統", layout="centered")

# 💡 終極 CSS：移除 +/- 按鈕，強制手機橫向
st.markdown("""
    <style>
    /* 1. 移除數字輸入框的控制按鈕 (加減號) */
    button.step-up, button.step-down { display: none !important; }
    div[data-testid="stNumberInputStepUp"], div[data-testid="stNumberInputStepDown"] {
        display: none !important;
    }
    
    /* 2. 強制橫向排版不堆疊 */
    [data-testid="column"] {
        flex: 1 1 0% !important;
        min-width: 0px !important;
    }
    div[data-testid="stHorizontalBlock"] > div:nth-child(1) { flex: 2 1 0% !important; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) { flex: 1 1 0% !important; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(3) { flex: 1 1 0% !important; }

    /* 3. 輸入框優化：直接顯示數字，無多餘外距 */
    .stNumberInput input {
        font-size: 16px !important;
        padding: 6px !important;
        text-align: center;
    }
    /* 隱藏輸入框標籤以節省版面 */
    div[data-testid="stNumberInput"] label { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

df_s, df_i = load_csv_safe(CSV_STORE), load_csv_safe(CSV_ITEMS)
if df_i is None or '品項' not in df_i.columns:
    st.error("❌ CSV 缺少 '品項' 欄位，請檢查檔案"); st.stop()

# 建立顯示名稱對照字典
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
            if st.button(f"📍 {s}", key=f"btn_{s}", use_container_width=True):
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
    if st.button("📄 產生進貨報表", type="primary", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "export"; st.rerun()
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_store"; st.rerun()

elif st.session_state.step == "fill_items":
    st.title(f"📝 {st.session_state.vendor}")
    v_col = '廠商名稱' if '廠商名稱' in df_i.columns else '廠商'
    items = df_i[df_i[v_col] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    # 💡 手機版自定義表頭
    h1, h2, h3 = st.columns([2, 1, 1])
    h1.caption("**品項名稱**")
    h2.caption("**庫存**")
    h3.caption("**進貨**")
    st.write("---")

    with st.form("inventory_form"):
        temp_data = []
        for _, row in items.iterrows():
            full_name = str(row['品項']).strip()
            # 💡 讀取清潔名稱用於輸入頁面顯示
            display_name = item_display_map.get(full_name, full_name)
            unit = str(row['單位']).strip() if '單位' in row else ""
            price = pd.to_numeric(row.get('單價', 0), errors='coerce')
            
            # 歷史庫存抓取
            prev_s, prev_p = 0, 0
            if not hist_df.empty:
                past = hist_df[(hist_df[COL_MAP['store_name']] == st.session_state.store) & (hist_df[COL_MAP['item_name']] == full_name)]
                if not past.empty:
                    latest = past.iloc[-1]
                    prev_s = int(pd.to_numeric(latest.get(COL_MAP['this_stock'], 0), errors='coerce') or 0)
                    prev_p = int(pd.to_numeric(latest.get(COL_MAP['this_purchase'], 0), errors='coerce') or 0)
            
            # 💡 橫向排列：品項(2) | 庫存(1) | 進貨(1)
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                st.markdown(f"**{display_name}**")
                st.caption(f"{unit} (前:{prev_s+prev_p})")
            with c2:
                # 💡 庫存輸入框 (移除加減按鈕)
                t_s = st.number_input("庫", min_value=0, step=1, key=f"s_{full_name}")
            with c3:
                # 💡 進貨輸入框 (移除加減按鈕)
                t_p = st.number_input("進", min_value=0, step=1, key=f"p_{full_name}")
            
            usage = (prev_s + prev_p) - t_s
            if t_s > 0 or t_p > 0:
                temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, full_name, unit, int(prev_s), int(prev_p), int(t_s), int(t_p), int(usage), float(price), float(round(t_p * price, 1))])
        
        st.write("---")
        if st.form_submit_button("💾 儲存並同步到雲端", use_container_width=True):
            if temp_data and sync_to_cloud(pd.DataFrame(temp_data)):
                st.success("✅ 儲存成功！"); st.session_state.step = "select_vendor"; st.rerun()
            else: st.warning("請填寫數據。")
        if st.form_submit_button("❌ 放棄並返回", use_container_width=True):
            st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "export":
    st.title("📋 進貨報表匯總")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    date_str = str(st.session_state.record_date)
    if not hist_df.empty:
        hist_df[COL_MAP['record_date']] = hist_df[COL_MAP['record_date']].astype(str)
        # 篩選今日進貨數據
        recs = hist_df[(hist_df[COL_MAP['store_name']] == st.session_state.store) & 
                       (hist_df[COL_MAP['record_date']] == date_str) & 
                       (pd.to_numeric(hist_df[COL_MAP['this_purchase']], errors='coerce') > 0)].copy()
        
        if recs.empty: st.warning("今日尚無進貨紀錄。")
        else:
            output = f"{date_str}\n{st.session_state.store}\n"
            for v in recs[COL_MAP['vendor_name']].unique():
                output += f"\n{v}\n"
                for _, r in recs[recs[COL_MAP['vendor_name']] == v].iterrows():
                    # 💡 報表顯示：將長品項名轉化為簡潔「品項名稱」
                    full_name = r[COL_MAP['item_name']]
                    disp_name = item_display_map.get(full_name, full_name)
                    u = r[COL_MAP['unit']]
                    p = int(pd.to_numeric(r[COL_MAP['unit_price']], errors='coerce') or 0)
                    q = int(pd.to_numeric(r[COL_MAP['this_purchase']], errors='coerce') or 0)
                    output += f"● {disp_name} ( {u} )-${p}：{q}{u}\n"
            st.text_area("📱 LINE 複製格式", value=output, height=300)
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()
