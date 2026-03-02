# ============================================================
# [A0] Imports
# ============================================================
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

# 圖表檢查
try:
    import plotly.express as px
    HAS_PLOTLY = True
except:
    HAS_PLOTLY = False

# ============================================================
# [A1] Config - 戰略設定層
# ============================================================
SHEET_ID = "1c9twPCyOumPKSau5xgUShJJAG-D9aaZBhK2FWBl2zwc"
CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv")
CSV_STORE = Path("品項總覽.xlsx - 分店.csv")
CSV_PRICE = Path("品項總覽.xlsx - 價格歷史.csv")

# ============================================================
# [A2] Global UI Style - 【Paul 的物理鎖定標準畫面】
# ============================================================
def apply_global_style():
    st.set_page_config(page_title="ROS 營運系統", layout="centered")
    st.markdown("""
        <style>
        /* 1. 物理移除表格序號 (0, 1, 2...) */
        [data-testid="stTable"] td:nth-child(1), [data-testid="stTable"] th:nth-child(1),
        [data-testid="stDataFrame"] [role="row"] [role="gridcell"]:first-child { display: none !important; }

        /* 2. 【核心鎖定】強制 fill_items 頁面三欄同列物理比例 (6:1:1) */
        [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-flow: row nowrap !important;
            align-items: center !important;
            gap: 0.5rem !important;
        }
        /* 第一欄：品項名稱，自動撐開 */
        div[data-testid="stHorizontalBlock"] > div:nth-child(1) {
            flex: 1 1 auto !important;
            min-width: 0px !important;
        }
        /* 第二、三欄：庫存與進貨，物理鎖定寬度 */
        div[data-testid="stHorizontalBlock"] > div:nth-child(2),
        div[data-testid="stHorizontalBlock"] > div:nth-child(3) {
            flex: 0 0 75px !important;
            min-width: 75px !important;
            max-width: 75px !important;
        }

        /* 3. 徹底移除數字框按鈕、標籤與外距，還原現場直覺 */
        div[data-testid="stNumberInputStepUp"], div[data-testid="stNumberInputStepDown"] { display: none !important; }
        div[data-testid="stNumberInput"] label { display: none !important; }
        input[type=number] { 
            -moz-appearance: textfield !important; 
            -webkit-appearance: none !important; 
            margin: 0 !important; 
            padding: 4px !important;
        }

        /* 4. 字體標準 */
        .stCaption { font-size: 11px !important; line-height: 1.1 !important; }
        b { font-size: 15px !important; }
        </style>
        """, unsafe_allow_html=True)

# ============================================================
# [B1] Cloud IO - 事實儲存 (Google Sheets)
# ============================================================
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds_info = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        return gspread.authorize(creds)
    except: return None

def get_worksheet_data(sheet_name):
    try:
        client = get_gspread_client()
        ws = client.open_by_key(SHEET_ID).worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        num_cols = ["上次剩餘", "上次叫貨", "本次剩餘", "本次叫貨", "期間消耗", "單價", "總金額"]
        for c in num_cols:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        return df
    except: return pd.DataFrame()

# ============================================================
# [C1] 核心引擎 - 【事實鎖定 Snapshot Price】
# ============================================================
def load_csv_safe(path):
    for enc in ["utf-8-sig", "utf-8", "cp950"]:
        try: return pd.read_csv(path, encoding=enc).map(lambda x: str(x).strip() if isinstance(x, str) else x)
        except: continue
    return None

def get_snapshot_price(item_id, target_date, price_df):
    """【哲學：事實不可被 Config 覆寫】抓取該日期有效的單價"""
    if price_df is None or price_df.empty: return 0.0
    try:
        df = price_df.copy()
        df["生效日"] = pd.to_datetime(df["生效日"]).dt.date
        # 找生效日 <= 盤點日 的最新一筆
        matched = df[(df["品項ID"] == str(item_id)) & (df["生效日"] <= target_date)]
        return float(matched.sort_values("生效日", ascending=False).iloc[0]["單價"]) if not matched.empty else 0.0
    except: return 0.0

# ============================================================
# [E1] 首頁 (分店) / [E2] 廠商中心
# ============================================================
def page_select_store(df_s):
    st.title("🏠 選擇分店")
    if df_s is not None:
        for s in df_s["分店名稱"].unique():
            if st.button(f"📍 {s}", key=f"s_{s}", use_container_width=True):
                st.session_state.store = s; st.session_state.step = "select_vendor"; st.rerun()

def page_select_vendor(df_i):
    st.title(f"🏢 {st.session_state.store}")
    st.session_state.record_date = st.date_input("🗓️ 盤點日期", value=st.session_state.record_date)
    if df_i is not None:
        vendors = sorted(df_i["廠商名稱"].unique())
        for i in range(0, len(vendors), 2):
            cols = st.columns(2)
            with cols[0]:
                if st.button(f"📦 {vendors[i]}", key=f"v_{vendors[i]}", use_container_width=True):
                    st.session_state.vendor = vendors[i]; st.session_state.history_df = get_worksheet_data("Records"); st.session_state.step = "fill_items"; st.rerun()
            if i + 1 < len(vendors):
                with cols[1]:
                    if st.button(f"📦 {vendors[i+1]}", key=f"v_{vendors[i+1]}", use_container_width=True):
                        st.session_state.vendor = vendors[i+1]; st.session_state.history_df = get_worksheet_data("Records"); st.session_state.step = "fill_items"; st.rerun()
    st.write("---")
    if st.button("📊 期間分析與歷史", use_container_width=True):
        st.session_state.history_df = get_worksheet_data("Records"); st.session_state.step = "analysis"; st.rerun()
    if st.button("⬅️ 返回", use_container_width=True):
        st.session_state.step = "select_store"; st.rerun()

# ============================================================
# [E3] 填寫頁面 - 【Paul 的標準畫面：三欄同列、防噪音、財務公式】
# ============================================================
def page_fill_items(df_i, df_pr, item_map):
    st.title(f"📝 {st.session_state.vendor}")
    items = df_i[df_i["廠商名稱"] == st.session_state.vendor]
    hist_df = st.session_state.get("history_df", pd.DataFrame())

    # 表頭標籤
    h1, h2, h3 = st.columns([6, 1, 1])
    h1.write("<b>品項名稱</b>", unsafe_allow_html=True)
    h2.write("<div style='text-align:center;'><b>庫</b></div>", unsafe_allow_html=True)
    h3.write("<div style='text-align:center;'><b>進</b></div>", unsafe_allow_html=True)

    with st.form("inventory_form", clear_on_submit=False):
        temp_data = []
        for _, row in items.iterrows():
            f_id, d_n = str(row["品項ID"]), str(row["品項名稱"])
            # 🚀 快照單價：事實鎖定
            price = get_snapshot_price(f_id, st.session_state.record_date, df_pr)
            if price == 0: price = pd.to_numeric(row.get('單價', 0), errors='coerce')
            
            p_s, p_p, suggest_qty = 0.0, 0.0, 0.0
            if not hist_df.empty:
                past = hist_df[(hist_df["店名"] == st.session_state.store) & (hist_df["品項ID"] == f_id)]
                if not past.empty:
                    latest = past.iloc[-1]
                    p_s, p_p = float(latest["本次剩餘"]), float(latest["本次叫貨"])
                    avg_usage = past["期間消耗"].tail(3).astype(float).mean() if not past.empty else 0.0
                    suggest_qty = max(0.0, (avg_usage * 1.5) - p_s)

            # 🚀 物理鎖定三欄同列渲染
            c1, c2, c3 = st.columns([6, 1, 1])
            with c1:
                st.write(f"<b>{d_n}</b>", unsafe_allow_html=True)
                st.caption(f"{row['單位']} (前結:{p_s:.1f} | 單價:{price:.1f} | 💡建議:{suggest_qty:.1f})")
            with c2: t_s = st.number_input("庫", key=f"s_{f_id}", step=0.1, value=None)
            with c3: t_p = st.number_input("進", key=f"p_{f_id}", step=0.1, value=None)
            
            temp_data.append({"f_id":f_id, "d_n":d_n, "unit":row["單位"], "p_s":p_s, "p_p":p_p, "t_s":t_s, "t_p":t_p, "price":price})

        if st.form_submit_button("💾 儲存Facts事實", use_container_width=True):
            valid_events = []
            for d in temp_data:
                # 【防噪音過濾】有點庫存(None 判定) 或 有進貨 才儲存
                if d["t_s"] is not None or (d["t_p"] is not None and d["t_p"] > 0):
                    ts_val = d["t_s"] if d["t_s"] is not None else 0.0
                    tp_val = d["t_p"] if d["t_p"] is not None else 0.0
                    # 🚀 財務定義消耗量公式：(上期剩餘 + 上期進貨) - 本期庫存
                    usage = (d["p_s"] + d["p_p"]) - ts_val if d["t_s"] is not None else 0.0
                    valid_events.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, d["f_id"], d["d_n"], d["unit"], d["p_s"], d["p_p"], ts_val, tp_val, usage, d["price"], round(tp_val * d["price"], 1)])
            
            if valid_events:
                client = get_gspread_client()
                client.open_by_key(SHEET_ID).worksheet("Records").append_rows(valid_events)
                st.success(f"✅ 已紀錄 {len(valid_events)} 項變動事實"); st.session_state.step = "select_vendor"; st.rerun()

    st.button("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"), use_container_width=True)

# [此處省略 E4-E6 頁面，因篇幅關係，將在對話中確保它們存在於你的完整版中]

# ============================================================
# [F1] Router / [G1] Main
# ============================================================
def main():
    apply_global_style()
    if "step" not in st.session_state: st.session_state.step = "select_store"
    if "record_date" not in st.session_state: st.session_state.record_date = date.today()
    df_s, df_i, df_pr = load_csv_safe(CSV_STORE), load_csv_safe(CSV_ITEMS), load_csv_safe(CSV_PRICE)
    
    s = st.session_state.step
    if s == "select_store": page_select_store(df_s)
    elif s == "select_vendor": page_select_vendor(df_i)
    elif s == "fill_items": page_fill_items(df_i, df_pr, {})
    # 待補齊 analysis 等頁面

if __name__ == "__main__":
    main()
