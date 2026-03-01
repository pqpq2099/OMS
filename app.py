import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

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
        st.error(f"⚠️ 金鑰錯誤: {e}"); return None

def get_cloud_data():
    try:
        client = get_gspread_client()
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet("Records")
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        for c in ['上次剩餘', '上次叫貨', '本次剩餘', '本次叫貨', '期間消耗', '單價', '總金額']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
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
# 2. 全域基礎樣式
# =========================
st.set_page_config(page_title="OMS 系統", layout="centered")
st.markdown("""
    <style>
    div[data-testid="stNumberInputStepUp"], div[data-testid="stNumberInputStepDown"], .stNumberInput button {
        display: none !important;
    }
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

# 💡 關鍵修正：使用「品項ID」作為映射的 Key
item_display_map = df_i.set_index('品項ID')['品項名稱'].to_dict()

if "step" not in st.session_state: st.session_state.step = "select_store"
if "record_date" not in st.session_state: st.session_state.record_date = date.today()

# =========================
# 3. 介面分流
# =========================

if st.session_state.step == "select_store":
    st.markdown("<style>.block-container { padding-top: 4rem !important; }</style>", unsafe_allow_html=True)
    st.title("🏠 選擇分店")
    if df_s is not None:
        for s in df_s['分店名稱'].unique():
            if st.button(f"📍 {s}", key=f"s_{s}", use_container_width=True):
                st.session_state.store = s; st.session_state.step = "select_vendor"; st.rerun()

elif st.session_state.step == "select_vendor":
    st.markdown("<style>.block-container { padding-top: 4rem !important; }</style>", unsafe_allow_html=True)
    st.title(f"🏢 {st.session_state.store}")
    st.session_state.record_date = st.date_input("🗓️ 盤點日期", value=st.session_state.record_date)
    vendors = sorted(df_i['廠商名稱'].unique())
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
    st.markdown("""
        <style>
        .block-container { padding-top: 2rem !important; padding-left: 0.3rem !important; padding-right: 0.3rem !important; }
        [data-testid="stHorizontalBlock"] { display: flex !important; flex-flow: row nowrap !important; align-items: center !important; }
        div[data-testid="stHorizontalBlock"] > div:nth-child(1) { flex: 1 1 auto !important; min-width: 0px !important; }
        div[data-testid="stHorizontalBlock"] > div:nth-child(2),
        div[data-testid="stHorizontalBlock"] > div:nth-child(3) { flex: 0 0 52px !important; min-width: 52px !important; max-width: 52px !important; }
        div[data-testid="stNumberInput"] label { display: none !important; }
        .stNumberInput input { font-size: 14px !important; padding: 4px 2px !important; text-align: center !important; }
        </style>
        """, unsafe_allow_html=True)
    
    st.title(f"📝 {st.session_state.vendor}")
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    if not hist_df.empty:
        ref_data = []
        # 💡 使用「品項ID」進行歷史匹配
        for f_id in items['品項ID'].unique():
            past = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['品項'] == f_id)]
            if not past.empty:
                latest = past.iloc[-1]
                ref_data.append({
                    "品項": latest.get('品項名稱', f_id),
                    "上剩": latest.get('本次剩餘', 0),
                    "上進": latest.get('本次叫貨', 0),
                    "消耗": latest.get('期間消耗', 0)
                })
        if ref_data:
            with st.expander("📊 查看上次歷史參考", expanded=True):
                st.dataframe(pd.DataFrame(ref_data), use_container_width=True, hide_index=True)
    
    st.write("---")
    h1, h2, h3 = st.columns([6, 1, 1])
    h1.caption("**品項**"); h2.caption("**庫**"); h3.caption("**進**")

    with st.form("inventory_form"):
        temp_data = []
        last_item_name = ""  # 紀錄上一個顯示的名稱
        
        for _, row in items.iterrows():
            f_id = str(row['品項ID']).strip() # 💡 改用「品項ID」作為唯一Key
            d_n = str(row['品項名稱']).strip() # 💡 改用「品項名稱」作為顯示
            unit = str(row['單位']).strip()
            price = pd.to_numeric(row.get('單價', 0), errors='coerce')
            
            p_s, p_p = 0.0, 0.0
            if not hist_df.empty:
                past = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['品項'] == f_id)]
                if not past.empty:
                    latest = past.iloc[-1]
                    p_s = float(latest.get('本次剩餘', 0)); p_p = float(latest.get('本次叫貨', 0))
            
            c1, c2, c3 = st.columns([6, 1, 1])
            with c1:
                # 💡 自動縮減重複名稱：若名稱相同，則顯示 └ 單位
                if d_n == last_item_name:
                    st.markdown(f"<span style='color:gray;'>└ </span> **{unit}**", unsafe_allow_html=True)
                else:
                    st.markdown(f"**{d_n}**")
                
                p_sum = p_s + p_p; p_show = int(p_sum) if p_sum.is_integer() else round(p_sum, 1)
                st.caption(f"{unit} (前:{p_show})")
                last_item_name = d_n # 更新紀錄
                
            with c2:
                # 💡 key 改用 f_id，徹底解決紅字當機
                t_s = st.number_input("庫", min_value=0.0, step=0.1, key=f"s_{f_id}", format="%g", value=None)
            with c3:
                t_p = st.number_input("進", min_value=0.0, step=0.1, key=f"p_{f_id}", format="%g", value=None)
            
            t_s_v = t_s if t_s is not None else 0.0; t_p_v = t_p if t_p is not None else 0.0
            usage = (p_s + p_p) - t_s_v
            # 存入時保留完整 ID 與名稱，確保分析準確
            temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, f_id, d_n, unit, p_s, p_p, t_s_v, t_p_v, usage, float(price), float(round(t_p_v * price, 1))])

        # 💡 按鈕縮排修復：確保在 form 範圍內
        if st.form_submit_button("💾 儲存並同步", use_container_width=True):
            valid = [d for d in temp_data if d[8] > 0 or d[9] > 0]
            if valid and sync_to_cloud(pd.DataFrame(valid)):
                st.success("✅ 儲存成功"); st.session_state.step = "select_vendor"; st.rerun()
                
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()

# --- 頁面 D：今日進貨明細 (格式保持) ---
elif st.session_state.step == "export":
    st.markdown("<style>.block-container { padding-top: 4rem !important; }</style>", unsafe_allow_html=True)
    st.title("📋 今日進貨明細")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    week_map = {0: '一', 1: '二', 2: '三', 3: '四', 4: '五', 5: '六', 6: '日'}
    delivery_date = st.session_state.record_date + timedelta(days=1)
    delivery_weekday = week_map[delivery_date.weekday()]
    header_date = f"{delivery_date.month}/{delivery_date.day}({delivery_weekday})"
    
    if not hist_df.empty:
        recs = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['日期'].astype(str) == str(st.session_state.record_date)) & (hist_df['本次叫貨'] > 0)]
        if not recs.empty:
            output = f"{header_date}\n"
            for v in recs['廠商'].unique():
                output += f"\n{v}\n{st.session_state.store}\n"
                for _, r in recs[recs['廠商'] == v].iterrows():
                    val = float(r['本次叫貨']); val_s = int(val) if val.is_integer() else val
                    output += f"{r['品項名稱']} {val_s} {r['單位']}\n"
                output += f"禮拜{delivery_weekday}到，謝謝\n"
            st.text_area("📱 LINE 複製", value=output, height=400)
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()

# --- 頁面 E：期間分析 (格式保持) ---
elif st.session_state.step == "analysis":
    st.markdown("<style>.block-container { padding-top: 4rem !important; }</style>", unsafe_allow_html=True)
    st.title("📊 期間進銷存分析")
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    start = st.date_input("起始", value=date.today()-timedelta(7)); end = st.date_input("結束", value=date.today())
    if not hist_df.empty:
        hist_df['日期'] = pd.to_datetime(hist_df['日期']).dt.date
        analysis = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['日期'] >= start) & (hist_df['日期'] <= end)]
        if not analysis.empty:
            summary = analysis.groupby(['廠商', '品項名稱', '單位', '單價']).agg({'期間消耗': 'sum', '本次叫貨': 'sum', '總金額': 'sum'}).reset_index()
            last_recs = analysis.sort_values('日期').groupby('品項名稱').tail(1)
            stock_map = last_recs.set_index('品項名稱')['本次剩餘'].to_dict()
            summary['期末庫存'] = summary['品項名稱'].map(stock_map).fillna(0)
            summary['庫存金額'] = summary['期末庫存'] * summary['單價']
            for c in ['期間消耗', '本次叫貨', '期末庫存']:
                summary[c] = summary[c].apply(lambda x: int(x) if x == int(x) else round(x, 1))
            
            buy_total, stock_total = f"{summary['總金額'].sum():,.1f}", f"{summary['庫存金額'].sum():,.1f}"
            st.markdown(f"""
                <div style='margin-bottom: 20px; border-left: 5px solid #1f77b4; padding-left: 15px;'>
                    <div style='margin-bottom: 5px;'><span style='font-size: 15px;'>採購支出總額：</span><span style='font-size: 20px; font-weight: 800; color: #4A90E2;'>${buy_total}</span></div>
                    <div><span style='font-size: 15px;'>期末庫存總值：</span><span style='font-size: 20px; font-weight: 800; color: #50C878;'>${stock_total}</span></div>
                </div>
            """, unsafe_allow_html=True)
            st.dataframe(summary, use_container_width=True)
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()
