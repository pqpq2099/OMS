import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

# =========================
# 1. 核心數據引擎
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
        st.error(f"⚠️ 連線失敗: {e}"); return None

def get_worksheet_data(sheet_name):
    try:
        client = get_gspread_client()
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

# =========================
# 2. 全域視覺標準 (終極鎖定：雙欄、無按鈕、單排)
# =========================
st.set_page_config(page_title="OMS 系統", layout="centered")
st.markdown("""
    <style>
    /* 1. 字體與標題 */
    html, body, [class*="css"], .stMarkdown, p, span, div, b {
        font-family: 'PingFang TC', 'Microsoft JhengHei', sans-serif !important;
        font-weight: 700 !important;
    }
    
    /* 2. 物理性消滅重疊文字與隱形標籤 */
    div[data-testid="stNumberInput"] label,
    div[data-testid="stWidgetLabel"],
    [aria-label^="arr_"], [aria-label^="val_"] {
        display: none !important;
        height: 0px !important;
        color: transparent !important;
    }

    /* 3. 徹底移除 +- 按鈕 (即便在手機端也強制隱藏) */
    div[data-testid="stNumberInputStepUp"], 
    div[data-testid="stNumberInputStepDown"],
    .stNumberInput button {
        display: none !important;
    }

    /* 4. 強制單排對齊樣式 */
    .stNumberInput input {
        font-weight: 800 !important;
        font-size: 16px !important;
        text-align: center !important;
        padding: 2px !important;
        min-height: 40px !important;
    }

    /* 5. 手機版強制雙欄廠商列表 (繞過 Streamlit 自動崩潰) */
    [data-testid="stVerticalBlock"] > div:has(div > button[key^="v_"]) {
        display: grid !important;
        grid-template-columns: 1fr 1fr !important;
        gap: 10px !important;
    }
    
    /* 修正列間距防止跑位 */
    div[data-testid="stHorizontalBlock"] {
        gap: 0.2rem !important;
    }
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
    st.write("<b>📦 作業廠商 (點擊進入)</b>", unsafe_allow_html=True)
    
    if df_i is not None:
        vendors = sorted(df_i['廠商名稱'].unique())
        # 💡 注意：這裡不再需要 columns(2)，CSS Grid 會自動接管 key="v_..." 的按鈕並強制雙欄
        for v in vendors:
            if st.button(v, key=f"v_{v}", use_container_width=True):
                st.session_state.vendor = v; 
                st.session_state.history_df = get_worksheet_data("Records")
                st.session_state.step = "fill_items"; st.rerun()
    
    st.write("---")
    st.write("<b>📊 數據控制中心</b>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📄 產生叫貨明細", type="primary", use_container_width=True):
            st.session_state.history_df = get_worksheet_data("Records"); st.session_state.step = "export"; st.rerun()
    with c2:
        if st.button("📈 進銷存分析", use_container_width=True):
            st.session_state.history_df = get_worksheet_data("Records"); st.session_state.step = "analysis"; st.rerun()
    
    if st.button("📜 查看歷史數據庫", use_container_width=True):
        st.session_state.view_df = get_worksheet_data(f"{st.session_state.store}_紀錄"); st.session_state.step = "view_history"; st.rerun()
    if st.button("⬅️ 返回分店列表", use_container_width=True): st.session_state.step = "select_store"; st.rerun()

elif st.session_state.step == "fill_items":
    if "vendor" not in st.session_state: st.session_state.step = "select_vendor"; st.rerun()
    st.markdown("<style>.block-container { padding-left: 0.1rem !important; padding-right: 0.1rem !important; }</style>", unsafe_allow_html=True)
    st.title(f"📝 {st.session_state.vendor}")
    
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    # 💡 強制 4.5:2:2 比例，給格子更多橫向空間
    h1, h2, h3 = st.columns([4.5, 2, 2])
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
                    latest = past.iloc[-1]; p_s = float(latest.get('本次剩餘', 0)); p_p = float(latest.get('本次叫貨', 0))
            
            c1, c2, c3 = st.columns([4.5, 2, 2])
            with c1:
                if d_n == last_item_name: st.write(f"<span style='color:gray;'>└ </span> <b>{unit}</b>", unsafe_allow_html=True)
                else: st.write(f"<b>{d_n}</b>", unsafe_allow_html=True)
                last_item_name = d_n
            # 💡 物理性隱藏 label 且不佔用任何像素高度，徹底消滅重疊
            with c2: t_s = st.number_input("", key=f"s_{f_id}", min_value=0.0, step=0.1, format="%g", value=0.0, label_visibility="collapsed")
            with c3: t_p = st.number_input("", key=f"p_{f_id}", min_value=0.0, step=0.1, format="%g", value=0.0, label_visibility="collapsed")
            
            t_s_v = t_s if t_s is not None else 0.0; t_p_v = t_p if t_p is not None else 0.0
            usage = (p_s + p_p) - t_s_v
            temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, f_id, d_n, unit, p_s, p_p, t_s_v, t_p_v, usage, float(price), float(round(t_p_v * price, 1))])

        if st.form_submit_button("💾 儲存盤點結果", use_container_width=True):
            valid = [d for d in temp_data if d[8] > 0 or d[9] > 0]
            sh = get_gspread_client().open_by_key(SHEET_ID)
            ws = sh.worksheet("Records"); ws.append_rows(valid)
            st.success("✅ 儲存成功"); st.session_state.step = "select_vendor"; st.rerun()
    st.button("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"))

# 其他分頁邏輯 (分析、報表、趨勢) 維持完整不變...
elif st.session_state.step == "analysis":
    st.title("📊 進銷存分析報表")
    a_df = get_worksheet_data("Records")
    start = st.date_input("開始日期", value=date.today()-timedelta(7)); end = st.date_input("結束日期", value=date.today())
    if not a_df.empty:
        a_df['日期'] = pd.to_datetime(a_df['日期']).dt.date
        filt = a_df[(a_df['店名'] == st.session_state.store) & (a_df['日期'] >= start) & (a_df['日期'] <= end)]
        if not filt.empty:
            summ = filt.groupby(['廠商', '品項名稱', '單位', '單價']).agg({'期間消耗': 'sum', '本次叫貨': 'sum', '總金額': 'sum'}).reset_index()
            last_recs = filt.sort_values('日期').groupby('品項名稱').tail(1)
            stock_map = last_recs.set_index('品項名稱')['本次剩餘'].to_dict()
            summ['期末庫存'] = summ['品項名稱'].map(stock_map).fillna(0); summ['庫存價值'] = summ['期末庫存'] * summ['單價']
            st.markdown(f"#### 💰 採購總值：${summ['總金額'].sum():,.1f} | 📦 庫存價值：${summ['庫存價值'].sum():,.1f}")
            st.dataframe(summ, use_container_width=True, hide_index=True)
    st.button("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"))

elif st.session_state.step == "export":
    st.title("📋 今日叫貨明細")
    h_df = get_worksheet_data("Records")
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
                    v_val = float(r['本次叫貨']); v_s = int(v_val) if v_val.is_integer() else v_val
                    out += f"{r['品項名稱']} {v_s} {r['單位']}\n"
                out += f"禮拜{week_map[deliv_date.weekday()]}到，謝謝\n"
            st.text_area("LINE 複製", value=out, height=350)
    st.button("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"))

elif st.session_state.step == "view_history":
    st.title(f"📜 {st.session_state.store} 歷史庫")
    v_df = st.session_state.get('view_df', pd.DataFrame())
    if not v_df.empty:
        t1, t2 = st.tabs(["📋 明細", "📈 趨勢"])
        with t1:
            s = st.text_input("🔍 搜尋品項")
            d_df = v_df.copy()
            if s: d_df = d_df[d_df.astype(str).apply(lambda x: x.str.contains(s)).any(axis=1)]
            st.dataframe(d_df.sort_values('日期', ascending=False), use_container_width=True, hide_index=True)
        with t2:
            try:
                import plotly.express as px
                tgt = st.selectbox("分析品項", options=sorted(v_df['品項名稱'].unique()))
                p_df = v_df[v_df['品項名稱'] == tgt].copy()
                p_df['日期'] = pd.to_datetime(p_df['日期']).dt.strftime('%Y-%m-%d')
                p_df = p_df.sort_values('日期')
                st.plotly_chart(px.line(p_df, x="日期", y="期間消耗", markers=True), use_container_width=True)
            except: st.info("圖表引擎加載中...")
    st.button("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"))
