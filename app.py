import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

# =========================
# 1. 核心設定 (對齊 Google 試算表欄位)
# =========================
SHEET_ID = '1c9twPCyOumPKSau5xgUShJJAG-D9aaZBhK2FWBl2zwc' 

COL_MAP = {
    'record_date': '日期',
    'store_name': '店名',
    'vendor_name': '廠商',
    'item_name': '品項',      # 數據庫主鍵：長名稱
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
        # 數值修正
        int_cols = [COL_MAP['this_stock'], COL_MAP['this_purchase'], COL_MAP['last_stock'], COL_MAP['last_purchase'], COL_MAP['usage_qty']]
        for col in df.columns:
            if col in int_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
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
# 2. 佈局樣式 (移除 +/- 與 強制橫向)
# =========================
st.set_page_config(page_title="OMS 進銷存系統", layout="centered")

st.markdown("""
    <style>
    /* 1. 隱藏步進按鈕 (+/-) */
    div[data-testid="stNumberInputStepUp"], div[data-testid="stNumberInputStepDown"] {
        display: none !important;
    }
    
    /* 2. 手機版強制橫向排版 (比例 2:1:1) */
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
    }
    [data-testid="column"] {
        min-width: 0px !important;
        flex: 1 1 0% !important;
    }
    div[data-testid="stHorizontalBlock"] > div:nth-child(1) { flex: 2 !important; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) { flex: 1 !important; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(3) { flex: 1 !important; }

    /* 3. 移除標籤並讓輸入框對齊 */
    div[data-testid="stNumberInput"] label { display: none !important; }
    .stNumberInput input {
        font-size: 16px !important;
        padding: 6px !important;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

CSV_STORE = Path("品項總覽.xlsx - 分店.csv")
CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv")

def load_csv_safe(path):
    for enc in ['utf-8-sig', 'utf-8', 'cp950', 'big5']:
        try:
            df = pd.read_csv(path, encoding=enc)
            df.columns = [str(c).strip() for c in df.columns]
            return df.map(lambda x: str(x).strip() if isinstance(x, str) else x)
        except: continue
    return None

df_s, df_i = load_csv_safe(CSV_STORE), load_csv_safe(CSV_ITEMS)
if df_i is None: st.error("❌ 品項檔讀取失敗"); st.stop()

# 映射字典： {長品項名: 乾淨品項名稱}
item_display_map = df_i.set_index('品項')['品項名稱'].to_dict()

if "step" not in st.session_state: st.session_state.step = "select_store"
if "record_date" not in st.session_state: st.session_state.record_date = date.today()

# =========================
# 3. 介面流程
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
    v_col = '廠商名稱' if '廠商名稱' in df_i.columns else '廠商'
    vendors = sorted(df_i[v_col].unique())
    for v in vendors:
        if st.button(f"📦 {v}", key=f"v_{v}", use_container_width=True):
            st.session_state.vendor = v; st.session_state.history_df = get_cloud_data()
            st.session_state.step = "fill_items"; st.rerun()
    st.write("---")
    # 💡 補回遺失的功能按鈕
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
    
    # 💡 標題與消耗量資訊
    h1, h2, h3 = st.columns([2, 1, 1])
    h1.write("**品項名稱**")
    h2.write("**庫存**")
    h3.write("**進貨**")
    st.write("---")

    with st.form("inventory_form"):
        temp_data = []
        for _, row in items.iterrows():
            full_n = str(row['品項']).strip()
            disp_n = item_display_map.get(full_n, full_n)
            unit = str(row['單位']).strip() if '單位' in row else ""
            price = pd.to_numeric(row.get('單價', 0), errors='coerce')
            
            p_s, p_p = 0, 0
            if not hist_df.empty:
                past = hist_df[(hist_df[COL_MAP['store_name']] == st.session_state.store) & (hist_df[COL_MAP['item_name']] == full_n)]
                if not past.empty:
                    latest = past.iloc[-1]
                    p_s = int(latest.get(COL_MAP['this_stock'], 0))
                    p_p = int(latest.get(COL_MAP['this_purchase'], 0))
            
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                st.write(f"**{disp_n}**")
                # 💡 期間消耗入口顯示
                st.caption(f"{unit} (前結:{p_s+p_p})")
            with c2:
                t_s = st.number_input("庫存", min_value=0, step=1, key=f"s_{full_n}")
            with c3:
                t_p = st.number_input("進貨", min_value=0, step=1, key=f"p_{full_n}")
            
            usage = (p_s + p_p) - t_s
            temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, full_n, unit, int(p_s), int(p_p), int(t_s), int(t_p), int(usage), float(price), float(round(t_p * price, 1))])

        st.write("---")
        if st.form_submit_button("💾 儲存並同步", use_container_width=True):
            valid = [d for d in temp_data if d[7] > 0 or d[8] > 0]
            if valid and sync_to_cloud(pd.DataFrame(valid)):
                st.success("✅ 儲存成功"); st.session_state.step = "select_vendor"; st.rerun()
    
    if st.button("⬅️ 返回廠商列表", use_container_width=True):
        st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "export":
    st.title("📋 今日進貨報表")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    date_str = str(st.session_state.record_date)
    if not hist_df.empty:
        hist_df[COL_MAP['record_date']] = hist_df[COL_MAP['record_date']].astype(str)
        recs = hist_df[(hist_df[COL_MAP['store_name']] == st.session_state.store) & (hist_df[COL_MAP['record_date']] == date_str) & (hist_df[COL_MAP['this_purchase']] > 0)].copy()
        
        if recs.empty: st.warning("今日尚無紀錄")
        else:
            # 💡 指定格式：● 品項名稱-$單價：數量單位
            output = f"{date_str}\n{st.session_state.store}\n"
            for v in recs[COL_MAP['vendor_name']].unique():
                output += f"\n{v}\n"
                for _, r in recs[recs[COL_MAP['vendor_name']] == v].iterrows():
                    d_n = item_display_map.get(r[COL_MAP['item_name']], r[COL_MAP['item_name']])
                    u, p, q = r[COL_MAP['unit']], int(r[COL_MAP['unit_price']]), int(r[COL_MAP['this_purchase']])
                    output += f"● {d_n}-${p}：{q}{u}\n"
            st.text_area("📱 LINE 複製格式", value=output, height=300)
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "analysis":
    st.title("📊 期間進銷存分析")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    c1, c2 = st.columns(2)
    start, end = c1.date_input("起始", value=date.today()-timedelta(7)), c2.date_input("結束", value=date.today())
    if not hist_df.empty:
        hist_df[COL_MAP['record_date']] = pd.to_datetime(hist_df[COL_MAP['record_date']]).dt.date
        analysis = hist_df[(hist_df[COL_MAP['store_name']] == st.session_state.store) & (hist_df[COL_MAP['record_date']] >= start) & (hist_df[COL_MAP['record_date']] <= end)].copy()
        if not analysis.empty:
            summary = analysis.groupby([COL_MAP['vendor_name'], COL_MAP['item_name'], COL_MAP['unit'], COL_MAP['unit_price']]).agg({COL_MAP['usage_qty']: 'sum', COL_MAP['total_price']: 'sum'}).reset_index()
            # 翻譯名稱
            summary['品項名稱'] = summary[COL_MAP['item_name']].map(lambda x: item_display_map.get(x, x))
            # 獲取最新庫存
            last_recs = analysis.sort_values(COL_MAP['record_date']).groupby(COL_MAP['item_name']).tail(1)
            stock_map = last_recs.set_index(COL_MAP['item_name'])[COL_MAP['this_stock']].to_dict()
            summary['庫存'] = summary[COL_MAP['item_name']].map(stock_map).fillna(0).astype(int)
            summary['庫存金額'] = summary['庫存'] * summary[COL_MAP['unit_price']]
            
            st.dataframe(summary[['廠商', '品項名稱', '單位', '單價', '期間消耗', '總金額', '庫存', '庫存金額']], use_container_width=True)
            m1, m2 = st.columns(2)
            m1.metric("採購總額", f"${summary[COL_MAP['total_price']].sum():,.0f}")
            m2.metric("庫存金額", f"${summary['庫存金額'].sum():,.0f}")
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()
