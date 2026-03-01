import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

import plotly.express as px  # 加入這一行
try:
    HAS_PLOTLY = True       # 💡 補上這行
except ImportError:
    HAS_PLOTLY = False      # 💡 補上這行
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
    /* 全域字體與重磅標題 */
    html, body, [class*="css"], .stMarkdown, p, span, div, b {
        font-family: 'PingFang TC', 'Microsoft JhengHei', sans-serif !important;
        font-weight: 700 !important;
    }
    h1, h2, h3 { font-weight: 800 !important; }
    
    /* 按鈕樣式加固 */
    .stButton button { font-weight: 700 !important; border-radius: 8px !important; }

    /* 輸入框視覺鎖定：800權重、16px字體、居中對齊 */
    .stNumberInput input {
        font-weight: 800 !important;
        font-size: 16px !important;
        text-align: center !important;
    }

    /* 物理移除：徹底消除 +- 按鈕與原生描述，確保純淨格子 */
    div[data-testid="stNumberInputStepUp"], 
    div[data-testid="stNumberInputStepDown"], 
    .stNumberInput button { 
        display: none !important; 
    }
    
    /* 移除數字框內建外距 */
    input[type=number] {
        -moz-appearance: textfield !important;
        -webkit-appearance: none !important;
        margin: 0 !important;
    }
    /* 💡 移除 st.table 左側的索引序號與縮小字體 */
    table th:first-child, table td:first-child {
        display: none !important;
    }
    .small-table table {
        font-size: 12px !important; /* 縮小字體至 12px */
    }
    .small-table th {
        padding: 4px !important;
        background-color: #f0f2f6 !important;
    }
    .small-table td {
        padding: 4px !important;
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
if df_i is not None:
    item_display_map = df_i.drop_duplicates('品項ID').set_index('品項ID')['品項名稱'].to_dict()

if "step" not in st.session_state: st.session_state.step = "select_store"
if "record_date" not in st.session_state: st.session_state.record_date = date.today()

# =========================
# 3. 介面分流
# =========================

# --- 步驟 1：選擇分店 ---
if st.session_state.step == "select_store":
    st.markdown("<style>.block-container { padding-top: 4rem !important; }</style>", unsafe_allow_html=True)
    st.title("🏠 選擇分店")
    if df_s is not None:
        for s in df_s['分店名稱'].unique():
            if st.button(f"📍 {s}", key=f"s_{s}", use_container_width=True):
                st.session_state.store = s; st.session_state.step = "select_vendor"; st.rerun()

# --- 步驟 2：廠商與功能中心 ---
elif st.session_state.step == "select_vendor":
    st.markdown("<style>.block-container { padding-top: 4rem !important; }</style>", unsafe_allow_html=True)
    st.title(f"🏢 {st.session_state.store}")
    st.session_state.record_date = st.date_input("🗓️ 盤點日期", value=st.session_state.record_date)
    
    # 廠商按鈕
    if df_i is not None:
        vendors = sorted(df_i['廠商名稱'].unique())
        for v in vendors:
            if st.button(f"📦 {v}", key=f"v_{v}", use_container_width=True):
                st.session_state.vendor = v; st.session_state.history_df = get_cloud_data()
                st.session_state.step = "fill_items"; st.rerun()
    
    st.write("---")
    st.write("<b>📊 報表與分析中心</b>", unsafe_allow_html=True)
    if st.button("📄 產生今日進貨明細", type="primary", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "export"; st.rerun()
    
    if st.button("📈 期間進銷存分析", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "analysis"; st.rerun()
    
    history_sheet = f"{st.session_state.store}_紀錄"
    if st.button(f"📜 查看分店歷史紀錄", use_container_width=True):
        st.session_state.view_df = get_worksheet_data(history_sheet)
        st.session_state.step = "view_history"; st.rerun()
        
    if st.button("⬅️ 返回分店列表", use_container_width=True):
        st.session_state.step = "select_store"; st.rerun()

# --- 步驟 3：填寫盤點頁面 (核心對齊區) ---
elif st.session_state.step == "fill_items":
    # 💡 物理單排鎖定 CSS (保持您原本的樣式)
    st.markdown("""
        <style>
        .block-container { padding-top: 2rem !important; padding-left: 0.3rem !important; padding-right: 0.3rem !important; }
        [data-testid="stHorizontalBlock"] { display: flex !important; flex-flow: row nowrap !important; align-items: center !important; }
        div[data-testid="stHorizontalBlock"] > div:nth-child(1) { flex: 1 1 auto !important; min-width: 0px !important; }
        div[data-testid="stHorizontalBlock"] > div:nth-child(2),
        div[data-testid="stHorizontalBlock"] > div:nth-child(3) { flex: 0 0 72px !important; min-width: 72px !important; max-width: 72px !important; }
        div[data-testid="stNumberInput"] label { display: none !important; }
        </style>
        """, unsafe_allow_html=True)
    
    st.title(f"📝 {st.session_state.vendor}")
    
    # --- 💡 以下是蓋掉的部分：改用靜態表格防止亂碼 ---
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
    if not hist_df.empty:
        ref_list = []
        for f_id in items['品項ID'].unique():
            f_name = item_display_map.get(f_id, "")
            past = hist_df[(hist_df['店名'] == st.session_state.store) & 
                           ((hist_df['品項ID'].astype(str) == str(f_id)) | (hist_df['品項名稱'] == str(f_name)))]
            if not past.empty:
                latest = past.iloc[-1]
                ref_list.append({
                    "品項名稱": f_name, 
                    "上次進貨": round(float(latest.get('本次叫貨', 0)), 1), 
                    "期間消耗": round(float(latest.get('期間消耗', 0)), 1)
                })
        if ref_list:
            st.write("<b>📊 上次數據參考</b>", unsafe_allow_html=True)
            st.table(pd.DataFrame(ref_list)) # 💡 這裡改用 st.table 消滅亂碼
    
    st.write("---")
    # (後續填寫表單內容保持不變...)
    h1, h2, h3 = st.columns([6, 1, 1])
    h1.write("<b>品項名稱</b>", unsafe_allow_html=True)
    h2.write("<div style='text-align:center;'><b>庫存</b></div>", unsafe_allow_html=True)
    h3.write("<div style='text-align:center;'><b>進貨</b></div>", unsafe_allow_html=True)

    with st.form("inventory_form"):
        temp_data = []
        last_item_display_name = "" 
        for _, row in items.iterrows():
            f_id = str(row['品項ID']).strip()
            d_n = str(row['品項名稱']).strip() 
            unit = str(row['單位']).strip()
            price = pd.to_numeric(row.get('單價', 0), errors='coerce')
            
            # 獲取上次數據
            p_s, p_p = 0.0, 0.0
            if not hist_df.empty:
                past = hist_df[(hist_df['店名'] == st.session_state.store) & 
                               ((hist_df['品項ID'].astype(str) == f_id) | (hist_df['品項名稱'] == d_n))]
                if not past.empty:
                    latest = past.iloc[-1]
                    p_s = float(latest.get('本次剩餘', 0)); p_p = float(latest.get('本次叫貨', 0))
            
            c1, c2, c3 = st.columns([6, 1, 1])
            with c1:
                if d_n == last_item_display_name:
                    st.write(f"<span style='color:gray;'>└ </span> <b>{unit}</b>", unsafe_allow_html=True)
                else:
                    st.write(f"<b>{d_n}</b>", unsafe_allow_html=True)
                
                # 即使移除大表格，小提示標註依然保留在名稱下以利對帳
                p_sum = p_s + p_p; p_show = int(p_sum) if p_sum.is_integer() else round(p_sum, 1)
                st.caption(f"{unit} (前結:{p_show})")
                last_item_display_name = d_n
            
            with c2:
                # 使用 label_visibility="collapsed" 是解決文字重疊的關鍵戰略
                t_s = st.number_input("庫", min_value=0.0, step=0.1, key=f"s_{f_id}", format="%g", value=None, label_visibility="collapsed")
            with c3:
                t_p = st.number_input("進", min_value=0.0, step=0.1, key=f"p_{f_id}", format="%g", value=None, label_visibility="collapsed")
            
            t_s_v = t_s if t_s is not None else 0.0
            t_p_v = t_p if t_p is not None else 0.0
            usage = (p_s + p_p) - t_s_v
            temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, f_id, d_n, unit, p_s, p_p, t_s_v, t_p_v, usage, float(price), float(round(t_p_v * price, 1))])

        if st.form_submit_button("💾 儲存並同步數據", use_container_width=True):
            valid = [d for d in temp_data if d[8] > 0 or d[9] > 0]
            if valid and sync_to_cloud(pd.DataFrame(valid)):
                st.success("✅ 儲存成功"); st.session_state.step = "select_vendor"; st.rerun()
    
    if st.button("⬅️ 返回", use_container_width=True): st.session_state.step = "select_vendor"; st.rerun()

with t1:
            all_items_list = ["全部品項"] + sorted(v_df['品項名稱'].unique().tolist())
            selected_item = st.selectbox("請選擇品項查看細節", options=all_items_list)
            
            d_df = v_df.copy()
            if selected_item != "全部品項":
                d_df = d_df[d_df['品項名稱'] == selected_item]
            
            # 💡 數據降噪：隱藏「店名」與「品項ID」
            cols_to_drop = [c for c in ['店名', '品項ID'] if c in d_df.columns]
            if cols_to_drop:
                d_df = d_df.drop(columns=cols_to_drop)
            
            # 格式化數字到小數點第一位
            num_cols = d_df.select_dtypes(include=['number']).columns
            for col in num_cols:
                d_df[col] = d_df[col].apply(lambda x: f"{x:.1f}")
            
            # 💡 使用容器包裹表格，觸發上方 CSS 的 small-font 規則
            st.markdown('<div class="small-font">', unsafe_allow_html=True)
            st.table(d_df.sort_values('日期', ascending=False))
            st.markdown('</div>', unsafe_allow_html=True)
            
        with t2:
            if HAS_PLOTLY:
                tgt = st.selectbox("分析品項", options=sorted(v_df['品項名稱'].unique()), key="chart_select")
                p_df = v_df[v_df['品項名稱'] == tgt].copy()
                p_df['日期'] = pd.to_datetime(p_df['日期']).dt.strftime('%Y-%m-%d')
                p_df = p_df.sort_values('日期')
                fig = px.line(p_df, x="日期", y="期間消耗", markers=True, title=f"【{tgt}】消耗趨勢")
                fig.update_layout(xaxis_type='category', hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)
                
    st.button("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"))
# --- 今日進貨明細 ---
elif st.session_state.step == "export":
    st.title("📋 今日進貨明細")
    hist_df = get_cloud_data()
    week_map = {0:'一', 1:'二', 2:'三', 3:'四', 4:'五', 5:'六', 6:'日'}
    delivery_date = st.session_state.record_date + timedelta(days=1)
    header_date = f"{delivery_date.month}/{delivery_date.day}({week_map[delivery_date.weekday()]})"
    if not hist_df.empty:
        recs = hist_df[(hist_df['店名'] == st.session_state.store) & (hist_df['日期'].astype(str) == str(st.session_state.record_date)) & (hist_df['本次叫貨'] > 0)]
        if not recs.empty:
            output = f"{header_date}\n"
            for v in recs['廠商'].unique():
                output += f"\n{v}\n{st.session_state.store}\n"
                for _, r in recs[recs['廠商'] == v].iterrows():
                    val = float(r['本次叫貨']); val_s = int(val) if val.is_integer() else val
                    output += f"{r['品項名稱']} {val_s} {r['單位']}\n"
                output += f"禮拜{week_map[delivery_date.weekday()]}到，謝謝\n"
            st.text_area("📱 LINE 複製", value=output, height=400)
    st.button("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"))

# --- 進銷存分析 (垂直堆疊版) ---
elif st.session_state.step == "analysis":
    st.title("📊 進銷存分析")
    a_df = get_worksheet_data("Records")
    start = st.date_input("起始", value=date.today()-timedelta(7)); end = st.date_input("結束", value=date.today())
    if not a_df.empty:
        a_df['日期'] = pd.to_datetime(a_df['日期']).dt.date
        filt = a_df[(a_df['店名'] == st.session_state.store) & (a_df['日期'] >= start) & (a_df['日期'] <= end)]
        if not filt.empty:
            summ = filt.groupby(['廠商', '品項名稱', '單位', '單價']).agg({'期間消耗': 'sum', '本次叫貨': 'sum', '總金額': 'sum'}).reset_index()
            last_recs = filt.sort_values('日期').groupby('品項名稱').tail(1)
            stock_map = last_recs.set_index('品項名稱')['本次剩餘'].to_dict()
            summ['期末庫存'] = summ['品項名稱'].map(stock_map).fillna(0)
            summ['庫存金額'] = summ['期末庫存'] * summ['單價']
            
            st.markdown(f"""
                <div style='background: #f8f9fa; padding: 15px; border-radius: 12px; border-left: 6px solid #4A90E2; margin-bottom: 12px;'>
                    <div style='font-size: 14px; color: #666; font-weight: 700;'>💰 目前採購支出總額</div>
                    <div style='font-size: 24px; color: #4A90E2; font-weight: 800;'>${summ['總金額'].sum():,.1f}</div>
                </div>
                <div style='background: #f8f9fa; padding: 15px; border-radius: 12px; border-left: 6px solid #50C878; margin-bottom: 25px;'>
                    <div style='font-size: 14px; color: #666; font-weight: 700;'>📦 目前剩餘庫存總值</div>
                    <div style='font-size: 24px; color: #50C878; font-weight: 800;'>${summ['庫存金額'].sum():,.1f}</div>
                </div>
            """, unsafe_allow_html=True)
            st.dataframe(summ, use_container_width=True, hide_index=True)
    st.button("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"))













