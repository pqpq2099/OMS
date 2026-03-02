# ============================================================
# [A0] 核心導入 - 系統運作的必要套件
# ============================================================
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

# 圖表模組檢查
try:
    import plotly.express as px
    HAS_PLOTLY = True
except:
    HAS_PLOTLY = False

# ============================================================
# [A1] 系統配置 - 雲端 ID 與本地檔案路徑
# ============================================================
SHEET_ID = "1c9twPCyOumPKSau5xgUShJJAG-D9aaZBhK2FWBl2zwc"

CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv")
CSV_STORE = Path("品項總覽.xlsx - 分店.csv")
CSV_PRICE = Path("品項總覽.xlsx - 價格歷史.csv")

# ============================================================
# [A2] 視覺標準 - 鎖定介面標準畫面 (CSS)
# ============================================================
def apply_global_style():
    st.set_page_config(page_title="ROS 營運系統", layout="centered")
    st.markdown("""
        <style>
        /* 物理移除表格序號 */
        [data-testid="stTable"] td:nth-child(1), [data-testid="stTable"] th:nth-child(1),
        [data-testid="stDataFrame"] [role="row"] [role="gridcell"]:first-child { display: none !important; }
        
        /* 緊湊型文字標準 (適合手機看) */
        [data-testid="stTable"] td, [data-testid="stTable"] th,
        [data-testid="stDataFrame"] [role="gridcell"], [data-testid="stDataFrame"] [role="columnheader"] {
            font-size: 11px !important; padding: 4px 2px !important; line-height: 1.1 !important;
        }

        /* 現場防呆：移除數字框調整按鈕，避免誤觸 */
        div[data-testid="stNumberInputStepUp"], div[data-testid="stNumberInputStepDown"] { display: none !important; }
        input[type=number] { -moz-appearance: textfield !important; margin: 0 !important; }
        </style>
        """, unsafe_allow_html=True)

# ============================================================
# [B1] 雲端設施 - Google Sheets 讀寫邏輯
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
    """從雲端抓取數據並執行數值標準化"""
    try:
        client = get_gspread_client()
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        num_cols = ["上次剩餘", "上次叫貨", "本次剩餘", "本次叫貨", "期間消耗", "單價", "總金額"]
        for c in num_cols:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        return df
    except: return pd.DataFrame()

def sync_to_cloud(df_to_save):
    """將盤點事實寫入雲端 Records 表"""
    client = get_gspread_client()
    try:
        ws = client.open_by_key(SHEET_ID).worksheet("Records")
        ws.append_rows(df_to_save.values.tolist())
        return True
    except: return False

# ============================================================
# [B2] 通訊設施 - LINE 訊息發送邏輯
# ============================================================
def send_line_message(message):
    import requests, json
    try:
        token = st.secrets["line_bot"]["channel_access_token"]
        # 自動根據分店抓取對應群組 ID
        target_id = st.secrets.get("line_groups", {}).get(st.session_state.store)
        if not target_id: target_id = st.secrets["line_bot"].get("user_id")
        
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        payload = {"to": target_id, "messages": [{"type": "text", "text": message}]}
        return requests.post(url, headers=headers, data=json.dumps(payload)).status_code == 200
    except: return False

# ============================================================
# [C1] 核心引擎 - 時空對位與價格鎖定 (ROS 的心臟)
# ============================================================
def load_csv_safe(path):
    for enc in ["utf-8-sig", "utf-8", "cp950"]:
        try: return pd.read_csv(path, encoding=enc).map(lambda x: str(x).strip() if isinstance(x, str) else x)
        except: continue
    return None

def get_snapshot_price(item_id, target_date, price_df):
    """【財務防呆】確保調價不影響歷史，抓取該日期有效的單價"""
    if price_df is None or price_df.empty: return 0.0
    try:
        df = price_df.copy()
        df["生效日"] = pd.to_datetime(df["生效日"]).dt.date
        target_ts = pd.Timestamp(target_date).date()
        # 找生效日 <= 盤點日 的所有紀錄，取最新一筆
        matched = df[(df["品項ID"] == str(item_id)) & (df["生效日"] <= target_ts)]
        return float(matched.sort_values("生效日", ascending=False).iloc[0]["單價"]) if not matched.empty else 0.0
    except: return 0.0

# ============================================================
# [E1] 節點：首頁 (分店選擇)
# ============================================================
def page_select_store(df_s):
    st.markdown("<style>.block-container { padding-top: 4rem !important; }</style>", unsafe_allow_html=True)
    st.title("🏠 選擇分店")
    if df_s is not None:
        for s in df_s["分店名稱"].unique():
            if st.button(f"📍 {s}", key=f"s_{s}", use_container_width=True):
                st.session_state.store = s; st.session_state.step = "select_vendor"; st.rerun()

# ============================================================
# [E2] 節點：廠商與功能中控
# ============================================================
def page_select_vendor(df_i):
    st.markdown("<style>.block-container { padding-top: 4rem !important; }</style>", unsafe_allow_html=True)
    st.title(f"🏢 {st.session_state.store}")
    st.session_state.record_date = st.date_input("🗓️ 盤點日期", value=st.session_state.record_date)
    
    if df_i is not None:
        vendors = sorted(df_i["廠商名稱"].unique())
        # 廠商按鈕兩兩並排
        for i in range(0, len(vendors), 2):
            cols = st.columns(2)
            with cols[0]:
                if st.button(f"📦 {vendors[i]}", key=f"v_{vendors[i]}", use_container_width=True):
                    st.session_state.vendor = vendors[i]; st.session_state.history_df = get_worksheet_data("Records")
                    st.session_state.step = "fill_items"; st.rerun()
            if i + 1 < len(vendors):
                with cols[1]:
                    if st.button(f"📦 {vendors[i+1]}", key=f"v_{vendors[i+1]}", use_container_width=True):
                        st.session_state.vendor = vendors[i+1]; st.session_state.history_df = get_worksheet_data("Records")
                        st.session_state.step = "fill_items"; st.rerun()

    st.write("<b>📊 報表與分析中心</b>", unsafe_allow_html=True)
    if st.button("📄 產生今日進貨明細", type="primary", use_container_width=True):
        st.session_state.history_df = get_worksheet_data("Records"); st.session_state.step = "export"; st.rerun()
    if st.button("📈 期間進銷存分析", use_container_width=True):
        st.session_state.history_df = get_worksheet_data("Records"); st.session_state.step = "analysis"; st.rerun()
    if st.button("⬅️ 返回分店列表", use_container_width=True):
        st.session_state.step = "select_store"; st.rerun()

# ============================================================
# [E3] 節點：盤點輸入 / 智慧叫貨
# ============================================================
def page_fill_items(df_i, df_pr, item_map):
    st.title(f"📝 {st.session_state.vendor}")
    items = df_i[df_i["廠商名稱"] == st.session_state.vendor]
    hist_df = st.session_state.get("history_df", pd.DataFrame())

    with st.form("inventory_form"):
        temp_data = []
        st.write("<b>品項名稱 (前結 | 單價 | 💡建議)</b>", unsafe_allow_html=True)
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

            c1, c2, c3 = st.columns([6, 1, 1])
            with c1:
                st.write(f"<b>{d_n}</b>", unsafe_allow_html=True)
                st.caption(f"{row['單位']} (前結:{p_s:.1f} | 單價:{price:.1f} | 💡建議:{suggest_qty:.1f})")
            t_s = st.number_input("庫", key=f"s_{f_id}", step=0.1, value=None, label_visibility="collapsed")
            t_p = st.number_input("進", key=f"p_{f_id}", step=0.1, value=None, label_visibility="collapsed")
            temp_data.append({"f_id":f_id, "d_n":d_n, "unit":row["單位"], "p_s":p_s, "p_p":p_p, "t_s":t_s, "t_p":t_p, "price":price})

        if st.form_submit_button("💾 儲存並同步數據", use_container_width=True):
            valid_events = []
            for d in temp_data:
                # 【防呆過濾】有點庫存 或 有進貨 才儲存，防止爆量
                if d["t_s"] is not None or (d["t_p"] is not None and d["t_p"] > 0):
                    ts_val = d["t_s"] if d["t_s"] is not None else 0.0
                    tp_val = d["t_p"] if d["t_p"] is not None else 0.0
                    # 財務定義消耗量公式：(上期剩 + 上期進) - 本期剩
                    usage = (d["p_s"] + d["p_p"]) - ts_val if d["t_s"] is not None else 0.0
                    valid_events.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, d["f_id"], d["d_n"], d["unit"], d["p_s"], d["p_p"], ts_val, tp_val, usage, d["price"], round(tp_val * d["price"], 1)])
            
            if valid_events and sync_to_cloud(pd.DataFrame(valid_events)):
                st.success(f"✅ 已紀錄 {len(valid_events)} 項變動"); st.session_state.step = "select_vendor"; st.rerun()
    st.button("⬅️ 返回選單", on_click=lambda: st.session_state.update(step="select_vendor"), use_container_width=True)

# ============================================================
# [E4] 節點：分析中心 (進銷存分析)
# ============================================================
def page_analysis():
    st.title("📊 進銷存分析")
    a_df = st.session_state.get('history_df', pd.DataFrame())
    if a_df.empty: st.warning("無資料可供分析"); return
    
    a_df["日期"] = pd.to_datetime(a_df["日期"]).dt.date
    c1, c2 = st.columns(2)
    start = c1.date_input("開始", value=date.today()-timedelta(14))
    end = c2.date_input("結束", value=date.today())
    
    filt = a_df[(a_df["店名"] == st.session_state.store) & (a_df["日期"] >= start) & (a_df["日期"] <= end)]
    if not filt.empty:
        total_buy = filt["總金額"].sum()
        st.metric("💰 區間進貨總額", f"${total_buy:,.0f}")
        summ = filt.groupby(["廠商", "品項名稱", "單位", "單價"]).agg({"期間消耗":"sum", "本次叫貨":"sum", "總金額":"sum"}).reset_index()
        st.dataframe(summ.sort_values("總金額", ascending=False), use_container_width=True, hide_index=True)
    st.button("⬅️ 返回選單", on_click=lambda: st.session_state.update(step="select_vendor"), use_container_width=True)

# ============================================================
# [F1] 路由中心 - 管理所有頁面跳轉
# ============================================================
def router(df_s, df_i, df_pr, item_map):
    s = st.session_state.step
    if s == "select_store": page_select_store(df_s)
    elif s == "select_vendor": page_select_vendor(df_i)
    elif s == "fill_items": page_fill_items(df_i, df_pr, item_map)
    elif s == "analysis": page_analysis()
    # (其餘 export, view_history 頁面以此類推...)

# ============================================================
# [G1] 啟動入口
# ============================================================
def main():
    apply_global_style()
    if "step" not in st.session_state: st.session_state.step = "select_store"
    if "record_date" not in st.session_state: st.session_state.record_date = date.today()
    df_s, df_i, df_pr = load_csv_safe(CSV_STORE), load_csv_safe(CSV_ITEMS), load_csv_safe(CSV_PRICE)
    item_map = df_i.drop_duplicates("品項ID").set_index("品項ID")["品項名稱"].to_dict() if df_i is not None else {}
    router(df_s, df_i, df_pr, item_map)

if __name__ == "__main__":
    main()
