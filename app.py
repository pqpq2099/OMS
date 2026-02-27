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
    'item_name': '品項',
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
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        # 數值型態強制轉型
        int_cols = [COL_MAP['this_stock'], COL_MAP['this_purchase'], COL_MAP['last_stock'], COL_MAP['last_purchase'], COL_MAP['usage_qty']]
        float_cols = [COL_MAP['unit_price'], COL_MAP['total_price']]
        for col in df.columns:
            if col in int_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            elif col in float_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float).round(1)
        return df
    except: return pd.DataFrame()

def sync_to_cloud(df_to_save):
    client = get_gspread_client()
    if not client: return False
    try:
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet("Records")
        headers = list(COL_MAP.values())
        ws.update('A1', [headers]) 
        ws.append_rows(df_to_save.values.tolist())
        return True
    except Exception as e:
        st.error(f"❌ 雲端寫入失敗: {e}"); return False

# =========================
# 2. 數據載入
# =========================
CSV_STORE = Path("品項總覽.xlsx - 分店.csv")
CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv")

def load_csv_safe(path):
    for enc in ['utf-8-sig', 'utf-8', 'cp950', 'big5']:
        try:
            df = pd.read_csv(path, encoding=enc)
            df.columns = [c.strip().replace('\ufeff', '') for c in df.columns]
            return df.map(lambda x: x.strip() if isinstance(x, str) else x)
        except: continue
    return None

st.set_page_config(page_title="進銷存管理系統", layout="centered")
df_s, df_i = load_csv_safe(CSV_STORE), load_csv_safe(CSV_ITEMS)

if "step" not in st.session_state: st.session_state.step = "select_store"
if "record_date" not in st.session_state: st.session_state.record_date = date.today()

# =========================
# 3. 介面流程
# =========================

if st.session_state.step == "select_store":
    st.title("🏠 選擇分店")
    if df_s is not None:
        for s in df_s['分店名稱'].unique():
            if st.button(f"📍 {s}", use_container_width=True):
                st.session_state.store = s
                st.session_state.step = "select_vendor"
                st.rerun()

elif st.session_state.step == "select_vendor":
    st.title(f"🏢 {st.session_state.store}")
    st.session_state.record_date = st.date_input("🗓️ 紀錄/送貨日期", value=st.session_state.record_date)
    
    st.subheader("📦 廠商列表")
    vendors = sorted(df_i['廠商名稱'].unique())
    for v in vendors:
        if st.button(f"📦 {v}", use_container_width=True):
            st.session_state.vendor = v
            st.session_state.history_df = get_cloud_data()
            st.session_state.step = "fill_items"
            st.rerun()
    
    st.write("---")
    st.subheader("📊 功能選單")
    if st.button("📄 產生今日叫貨報表", type="primary", use_container_width=True):
        st.session_state.history_df = get_cloud_data()
        st.session_state.step = "export"
        st.rerun()
    if st.button("📊 期間進銷存分析", use_container_width=True):
        st.session_state.history_df = get_cloud_data()
        st.session_state.step = "analysis"
        st.rerun()
    if st.button("⬅️ 返回分店列表", use_container_width=True):
        st.session_state.step = "select_store"
        st.rerun()

elif st.session_state.step == "fill_items":
    st.title(f"📝 {st.session_state.vendor}")
    st.caption(f"分店：{st.session_state.store} | 日期：{st.session_state.record_date}")
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    with st.form("inventory_form"):
        temp_data = []
        for _, row in items.iterrows():
            name = str(row['品項名稱']).strip()
            unit = str(row['單位']).strip() if '單位' in row and pd.notna(row['單位']) else ""
            price = float(row.get('單價', 0))
            
            prev_s, prev_p = 0, 0
            if not hist_df.empty:
                past = hist_df[(hist_df[COL_MAP['store_name']] == st.session_state.store) & (hist_df[COL_MAP['item_name']] == name)]
                if not past.empty:
                    latest = past.iloc[-1]
                    prev_s = int(latest.get(COL_MAP['this_stock'], 0))
                    prev_p = int(latest.get(COL_MAP['this_purchase'], 0))
            
            st.markdown(f"### {name}")
            st.markdown(f"**單位：{unit}** | **上次結餘：{int(prev_s + prev_p)}**")
            
            t_s = st.number_input(f"本次剩餘", min_value=0, step=1, key=f"s_{name}", format="%d")
            t_p = st.number_input(f"本次叫貨", min_value=0, step=1, key=f"p_{name}", format="%d")
            
            usage = (prev_s + prev_p) - t_s
            st.markdown(f"🧮 *計算使用量：{int(usage)}*")
            st.write("---")
            
            total_amt = round(t_p * price, 1)
            if t_s > 0 or t_p > 0:
                temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, name, unit, int(prev_s), int(prev_p), int(t_s), int(t_p), int(usage), float(price), float(total_amt)])
        
        submit = st.form_submit_button("💾 儲存並同步", use_container_width=True)
        cancel = st.form_submit_button("❌ 不叫貨返回", use_container_width=True)
        
        if submit:
            if temp_data:
                df_to_save = pd.DataFrame(temp_data)
                if sync_to_cloud(df_to_save):
                    st.success("✅ 同步成功！")
                    st.session_state.step = "select_vendor"; st.rerun()
            else: st.warning("未填寫數據。")
        if cancel:
            st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "export":
    st.title("📋 叫貨報表匯總")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    date_str = str(st.session_state.record_date)
    
    if not hist_df.empty:
        hist_df[COL_MAP['record_date']] = hist_df[COL_MAP['record_date']].astype(str)
        recs = hist_df[(hist_df[COL_MAP['store_name']] == st.session_state.store) & (hist_df[COL_MAP['record_date']] == date_str) & (hist_df[COL_MAP['this_purchase']] > 0)].copy()
        
        if recs.empty:
            st.warning(f"{date_str} 目前尚無叫貨紀錄。")
        else:
            st.subheader("🔍 當日叫貨與消耗參考")
            display_headers = [COL_MAP['vendor_name'], COL_MAP['item_name'], COL_MAP['usage_qty'], COL_MAP['this_purchase'], COL_MAP['total_price']]
            st.dataframe(recs[display_headers].rename(columns={COL_MAP['usage_qty']: '上次至今消耗', COL_MAP['total_price']: '本次叫貨金額'}), use_container_width=True)
            
            output = f"【{st.session_state.store}】叫貨單 ({date_str})\n"
            for v in recs[COL_MAP['vendor_name']].unique():
                output += f"\n廠商：{v}\n"
                for _, r in recs[recs[COL_MAP['vendor_name']] == v].iterrows():
                    u = str(r.get(COL_MAP['unit'], '')).strip()
                    output += f"● {r[COL_MAP['item_name']]}：{int(r[COL_MAP['this_purchase']])}{u} (前次消耗:{int(r[COL_MAP['usage_qty']])})\n"
            st.text_area("📱 LINE 複製格式", value=output, height=300)
    
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "analysis":
    st.title("📊 期間進銷存彙整")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    c1, c2 = st.columns(2)
    start = c1.date_input("起始日期", value=date.today()-timedelta(7))
    end = c2.date_input("結束日期", value=date.today())
    
    if not hist_df.empty:
        hist_df[COL_MAP['record_date']] = pd.to_datetime(hist_df[COL_MAP['record_date']]).dt.date
        analysis = hist_df[(hist_df[COL_MAP['store_name']] == st.session_state.store) & (hist_df[COL_MAP['record_date']] >= start) & (hist_df[COL_MAP['record_date']] <= end)].copy()
        
        if not analysis.empty:
            # 聚合計算
            summary = analysis.groupby([COL_MAP['vendor_name'], COL_MAP['item_name'], COL_MAP['unit'], COL_MAP['unit_price']]).agg({
                COL_MAP['usage_qty']: 'sum',
                COL_MAP['total_price']: 'sum'
            }).reset_index()
            
            # 獲取期末庫存
            last_records = analysis.sort_values(COL_MAP['record_date']).groupby(COL_MAP['item_name']).tail(1)
            stock_map = last_records.set_index(COL_MAP['item_name'])[COL_MAP['this_stock']].to_dict()
            
            summary['期末庫存'] = summary[COL_MAP['item_name']].map(stock_map).fillna(0).astype(int)
            # 💡 名稱修改：由「期末市值」改為「庫存金額」
            summary['庫存金額'] = summary['期末庫存'] * summary[COL_MAP['unit_price']]
            
            st.subheader(f"📅 期間匯總報表")
            st.dataframe(summary, use_container_width=True)
            
            st.write("---")
            m1, m2 = st.columns(2)
            m1.metric("採購支出總額", f"${summary[COL_MAP['total_price']].sum():,.0f}")
            # 💡 名稱修改：由「期末資產市值」改為「庫存金額」
            m2.metric("庫存金額", f"${summary['庫存金額'].sum():,.0f}")
        else: st.info("無數據。")
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()
