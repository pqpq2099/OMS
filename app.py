# ============================================================
# [A0] Imports
# ============================================================
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path

# Plotly (optional)
try:
    import plotly.express as px
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

# ============================================================
# [A1] Config - 你最常改的地方都放這裡
# ============================================================
SHEET_ID = "1c9twPCyOumPKSau5xgUShJJAG-D9aaZBhK2FWBl2zwc"

CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv")
CSV_STORE = Path("品項總覽.xlsx - 分店.csv")
CSV_PRICE = Path("品項總覽.xlsx - 價格歷史.csv")  # ⭐價格歷史

# ============================================================
# [A2] Global UI Style
# ============================================================
def apply_global_style():
    st.set_page_config(page_title="OMS 系統", layout="centered")
    st.markdown(
        """
        <style>
        /* 1. 物理移除：所有表格的最左側序號 (0, 1, 2...) */
        [data-testid="stTable"] td:nth-child(1),
        [data-testid="stTable"] th:nth-child(1),
        [data-testid="stDataFrame"] [role="row"] [role="gridcell"]:first-child {
            display: none !important;
        }

        /* 2. 歷史紀錄與庫存表格：縮小、變細、極度緊湊 */
        [data-testid="stTable"] td,
        [data-testid="stTable"] th,
        [data-testid="stDataFrame"] [role="gridcell"],
        [data-testid="stDataFrame"] [role="columnheader"] {
            font-size: 11px !important;
            font-weight: 400 !important;
            padding: 4px 2px !important;
            line-height: 1.1 !important;
        }

        /* 3. 表頭文字：稍微加重結構感 */
        [data-testid="stTable"] th,
        [data-testid="stDataFrame"] [role="columnheader"] {
            font-weight: 600 !important;
        }

        /* 4. 移除數字框內建按鈕與外距 */
        div[data-testid="stNumberInputStepUp"],
        div[data-testid="stNumberInputStepDown"] { display: none !important; }
        input[type=number] { -moz-appearance: textfield !important; -webkit-appearance: none !important; margin: 0 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# [B1] Cloud (Google Sheets) - 讀寫 Records
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
    except Exception as e:
        st.error(f"⚠️ 金鑰連線失敗: {e}")
        return None

def get_worksheet_data(sheet_name: str) -> pd.DataFrame:
    try:
        client = get_gspread_client()
        if not client: return pd.DataFrame()
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        num_cols = ["上次剩餘", "上次叫貨", "本次剩餘", "本次叫貨", "期間消耗", "單價", "總金額"]
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        return df
    except Exception:
        return pd.DataFrame()

def get_cloud_data() -> pd.DataFrame:
    return get_worksheet_data("Records")

def sync_to_cloud(df_to_save: pd.DataFrame) -> bool:
    client = get_gspread_client()
    if not client: return False
    try:
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet("Records")
        ws.append_rows(df_to_save.values.tolist())
        return True
    except Exception:
        return False

# ============================================================
# [B2] LINE Push
# ============================================================
def send_line_message(message: str) -> bool:
    import requests, json
    try:
        token = st.secrets["line_bot"]["channel_access_token"]
        current_store = st.session_state.get("store", "")
        target_id = st.secrets.get("line_groups", {}).get(current_store)
        if not target_id: target_id = st.secrets["line_bot"].get("user_id")
        if not target_id: return False
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        payload = {"to": target_id, "messages": [{"type": "text", "text": message}]}
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        return response.status_code == 200
    except Exception: return False

# ============================================================
# [C1] Local Data (CSV) - 讀取與價格邏輯
# ============================================================
def load_csv_safe(path: Path) -> pd.DataFrame | None:
    for enc in ["utf-8-sig", "utf-8", "cp950", "big5"]:
        try:
            df = pd.read_csv(path, encoding=enc)
            return df.map(lambda x: str(x).strip() if isinstance(x, str) else x)
        except Exception: continue
    return None

def get_price_by_date(item_id: str, target_date: date, price_df: pd.DataFrame | None) -> float:
    if price_df is None or price_df.empty: return 0.0
    df = price_df.copy()
    required = {"品項ID", "單價", "生效日"}
    if not required.issubset(set(df.columns)): return 0.0
    if "結束日" not in df.columns: df["結束日"] = pd.NaT
    df["品項ID"] = df["品項ID"].astype(str).str.strip()
    df["單價"] = pd.to_numeric(df["單價"], errors="coerce").fillna(0)
    df["生效日"] = pd.to_datetime(df["生效日"], errors="coerce")
    df["結束日"] = pd.to_datetime(df["結束日"], errors="coerce")
    target_ts = pd.Timestamp(target_date)
    matched = df[(df["品項ID"] == str(item_id).strip()) & (df["生效日"].notna()) & (df["生效日"] <= target_ts) & (df["結束日"].isna() | (df["結束日"] >= target_ts))].sort_values("生效日")
    return float(matched.iloc[-1]["單價"]) if not matched.empty else 0.0

def load_master_data():
    df_s = load_csv_safe(CSV_STORE)
    df_i = load_csv_safe(CSV_ITEMS)
    df_pr = load_csv_safe(CSV_PRICE)
    item_display_map = {}
    if df_i is not None and not df_i.empty:
        item_display_map = df_i.drop_duplicates("品項ID").set_index("品項ID")["品項名稱"].to_dict()
    return df_s, df_i, df_pr, item_display_map

# ============================================================
# [D1] Session State Init
# ============================================================
def init_session():
    if "step" not in st.session_state: st.session_state.step = "select_store"
    if "record_date" not in st.session_state: st.session_state.record_date = date.today()

# ============================================================
# [E1] select_store - 分店選擇頁
# ============================================================
def page_select_store(df_s: pd.DataFrame | None):
    st.markdown("<style>.block-container { padding-top: 4rem !important; }</style>", unsafe_allow_html=True)
    st.title("🏠 選擇分店")
    if df_s is None or df_s.empty:
        st.warning("⚠️ 分店資料讀取失敗"); return
    for s in df_s["分店名稱"].unique():
        if st.button(f"📍 {s}", key=f"s_{s}", use_container_width=True):
            st.session_state.store = s; st.session_state.step = "select_vendor"; st.rerun()

# ============================================================
# [E2] select_vendor - 廠商與功能中心
# ============================================================
def page_select_vendor(df_i: pd.DataFrame | None):
    st.markdown("<style>.block-container { padding-top: 4rem !important; }</style>", unsafe_allow_html=True)
    st.title(f"🏢 {st.session_state.store}")
    st.session_state.record_date = st.date_input("🗓️ 盤點日期", value=st.session_state.record_date)
    if df_i is not None:
        vendors = sorted(df_i["廠商名稱"].unique())
        for i in range(0, len(vendors), 2):
            cols = st.columns(2)
            with cols[0]:
                v_left = vendors[i]
                if st.button(f"📦 {v_left}", key=f"v_{v_left}", use_container_width=True):
                    st.session_state.vendor = v_left; st.session_state.history_df = get_cloud_data(); st.session_state.step = "fill_items"; st.rerun()
            if i + 1 < len(vendors):
                with cols[1]:
                    v_right = vendors[i + 1]
                    if st.button(f"📦 {v_right}", key=f"v_{v_right}", use_container_width=True):
                        st.session_state.vendor = v_right; st.session_state.history_df = get_cloud_data(); st.session_state.step = "fill_items"; st.rerun()
    st.write("<b>📊 報表與分析中心</b>", unsafe_allow_html=True)
    if st.button("📄 產生今日進貨明細", type="primary", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "export"; st.rerun()
    if st.button("📈 期間進銷存分析", use_container_width=True):
        st.session_state.history_df = get_cloud_data(); st.session_state.step = "analysis"; st.rerun()
    if st.button("📜 查看分店歷史紀錄", use_container_width=True):
        st.session_state.view_df = get_worksheet_data(f"{st.session_state.store}_紀錄"); st.session_state.step = "view_history"; st.rerun()
    if st.button("⬅️ 返回分店列表", use_container_width=True):
        st.session_state.step = "select_store"; st.rerun()

# ============================================================
# [E3] fill_items - 盤點輸入
# ============================================================
def page_fill_items(df_i: pd.DataFrame | None, df_pr: pd.DataFrame | None, item_display_map: dict):
    st.markdown("<style>.block-container { padding-top: 2rem !important; padding-left: 0.3rem !important; padding-right: 0.3rem !important; } [data-testid='stHorizontalBlock'] { display: flex !important; flex-flow: row nowrap !important; align-items: center !important; } div[data-testid='stHorizontalBlock'] > div:nth-child(1) { flex: 1 1 auto !important; min-width: 0px !important; } div[data-testid='stHorizontalBlock'] > div:nth-child(2), div[data-testid='stHorizontalBlock'] > div:nth-child(3) { flex: 0 0 72px !important; min-width: 72px !important; max-width: 72px !important; } div[data-testid='stNumberInput'] label { display: none !important; }</style>", unsafe_allow_html=True)
    st.title(f"📝 {st.session_state.vendor}")
    items = df_i[df_i["廠商名稱"] == st.session_state.vendor]
    hist_df = st.session_state.get("history_df", pd.DataFrame())
    if not hist_df.empty:
        ref_list = []
        for f_id in items["品項ID"].unique():
            f_name = item_display_map.get(f_id, "")
            past = hist_df[(hist_df["店名"].astype(str).str.strip() == str(st.session_state.store).strip()) & ((hist_df["品項ID"].astype(str).str.strip() == str(f_id).strip()) | (hist_df["品項名稱"].astype(str).str.strip() == str(f_name).strip()))]
            if not past.empty:
                latest = past.iloc[-1]
                p_p_val, p_u_val = pd.to_numeric(latest.get("本次叫貨", 0), errors="coerce"), pd.to_numeric(latest.get("期間消耗", 0), errors="coerce")
                if p_p_val > 0 or p_u_val > 0: ref_list.append({"品項名稱": f_name, "上次叫貨": round(float(p_p_val), 1), "期間消耗": round(float(p_u_val), 1)})
        if ref_list:
            with st.expander("📊 查看上次叫貨/消耗參考 (已自動隱藏無紀錄品項)", expanded=False):
                display_ref_df = pd.DataFrame(ref_list)
                for col in ["上次叫貨", "期間消耗"]: display_ref_df[col] = display_ref_df[col].apply(lambda x: f"{x:.1f}")
                st.table(display_ref_df)
    st.write("---")
    h1, h2, h3 = st.columns([6, 1, 1])
    h1.write("<b>品項名稱</b>", unsafe_allow_html=True); h2.write("<div style='text-align:center;'><b>庫</b></div>", unsafe_allow_html=True); h3.write("<div style='text-align:center;'><b>進</b></div>", unsafe_allow_html=True)
    with st.form("inventory_form"):
        temp_data = []
        last_item_display_name = ""
        for _, row in items.iterrows():
            f_id, d_n, unit = str(row["品項ID"]).strip(), str(row["品項名稱"]).strip(), str(row["單位"]).strip()
            default_price = pd.to_numeric(row.get("單價", 0), errors="coerce")
            price = get_price_by_date(f_id, st.session_state.record_date, df_pr) or float(default_price)
            p_s, p_p, avg_usage, suggest_qty = 0.0, 0.0, 0.0, 0.0
            if not hist_df.empty:
                past = hist_df[(hist_df["店名"].astype(str).str.strip() == str(st.session_state.store).strip()) & ((hist_df["品項ID"].astype(str).str.strip() == str(f_id).strip()) | (hist_df["品項名稱"].astype(str).str.strip() == str(d_n).strip()))].copy()
                if not past.empty:
                    latest = past.iloc[-1]
                    p_s, p_p = float(latest.get("本次剩餘", 0.0)), float(latest.get("本次叫貨", 0.0))
                    recent_usage = past["期間消耗"].tail(3).astype(float)
                    avg_usage = recent_usage.mean() if not recent_usage.empty else 0.0
                    suggest_qty = max(0.0, (avg_usage * 1.5) - p_s)
            c1, c2, c3 = st.columns([6, 1, 1])
            with c1:
                if d_n == last_item_display_name: st.write(f"<span style='color:gray;'>└ </span> <b>{unit}</b>", unsafe_allow_html=True)
                else: st.write(f"<b>{d_n}</b>", unsafe_allow_html=True)
                st.caption(f"{unit} (前結:{p_s:.1f} | 單價:{price:.1f} | 💡建議:{suggest_qty:.1f})")
                last_item_display_name = d_n
            with c2: t_s = st.number_input("庫", min_value=0.0, step=0.1, key=f"s_{f_id}", format="%g", value=None, label_visibility="collapsed")
            with c3: t_p = st.number_input("進", min_value=0.0, step=0.1, key=f"p_{f_id}", format="%g", value=None, label_visibility="collapsed")
            t_s_v, t_p_v = (t_s if t_s is not None else 0.0), (t_p if t_p is not None else 0.0)
            usage = p_s - t_s_v
            temp_data.append([str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, f_id, d_n, unit, p_s, p_p, t_s_v, t_p_v, usage, float(price), float(round(t_p_v * price, 1))])
        if st.form_submit_button("💾 儲存並同步數據", use_container_width=True):
            valid = [d for d in temp_data if d[8] >= 0 or d[9] > 0]
            if valid and sync_to_cloud(pd.DataFrame(valid)):
                st.success("✅ 儲存成功"); st.session_state.step = "select_vendor"; st.rerun()
    st.button("⬅️ 返回功能選單", on_click=lambda: st.session_state.update(step="select_vendor"), use_container_width=True, key="back_from_fill")

# ============================================================
# [E4] view_history - 歷史紀錄查詢
# ============================================================
def page_view_history():
    st.markdown("<style>[data-testid='stMainBlockContainer'] { max-width: 95% !important; padding-left: 0.5rem !important; padding-right: 0.5rem !important; } [data-testid='stDataFrame'] [role='gridcell'] { padding: 1px 2px !important; line-height: 1.0 !important; } [data-testid='stDataFrame'] [role='columnheader'] { padding: 2px 2px !important; font-size: 10px !important; }</style>", unsafe_allow_html=True)
    st.title(f"📜 {st.session_state.store} 歷史庫")
    v_df = st.session_state.get("view_df", pd.DataFrame())
    if v_df.empty:
        st.info("💡 尚無歷史紀錄可供查看。")
        if st.button("⬅️ 返回", use_container_width=True):
            st.session_state.step = "select_vendor"; st.rerun()
        return
    c_h_date1, c_h_date2 = st.columns(2)
    h_start = c_h_date1.date_input("起始日期", value=date.today() - timedelta(7), key="h_start")
    h_end = c_h_date2.date_input("結束日期", value=date.today(), key="h_end")
    t1, t2 = st.tabs(["📋 明細", "📈 趨勢"])
    with t1:
        v_df["日期_dt"] = pd.to_datetime(v_df["日期"]).dt.date
        temp_filt = v_df[(v_df["日期_dt"] >= h_start) & (v_df["日期_dt"] <= h_end)].copy()
        if temp_filt.empty: st.info("💡 此區間內無紀錄。")
        else:
            col_v, col_i = st.columns(2)
            all_v_m = ["全部廠商"] + sorted(temp_filt["廠商"].unique().tolist())
            sel_v_m = col_v.selectbox("📦 1. 選擇廠商", options=all_v_m, index=0, key="h_v_m_sel")
            f_df = temp_filt.copy()
            if sel_v_m != "全部廠商": f_df = f_df[f_df["廠商"] == sel_v_m]
            all_i_m = ["全部品項"] + sorted(f_df["品項名稱"].unique().tolist())
            sel_i_m = col_i.selectbox("🏷️ 2. 選擇品項", options=all_i_m, index=0, key="h_i_m_sel")
            if sel_i_m != "全部品項": f_df = f_df[f_df["品項名稱"] == sel_i_m]
            if "日期" in f_df.columns: f_df["顯示日期"] = pd.to_datetime(f_df["日期"]).dt.strftime("%m-%d")
            cols_order = ["顯示日期", "廠商", "品項名稱", "單位", "上次剩餘", "上次叫貨", "本次剩餘", "本次叫貨", "期間消耗"]
            final_cols = [c for c in cols_order if c in f_df.columns]
            st.dataframe(f_df[final_cols].sort_values("顯示日期", ascending=False), use_container_width=True, hide_index=True, column_config={"顯示日期": st.column_config.TextColumn("日期", width="minishort"), "廠商": st.column_config.TextColumn(width="small"), "品項名稱": st.column_config.TextColumn(width="medium"), "單位": st.column_config.TextColumn(width="minishort"), "上次剩餘": st.column_config.NumberColumn(format="%.1f", width="minishort"), "上次叫貨": st.column_config.NumberColumn(format="%.1f", width="minishort"), "本次剩餘": st.column_config.NumberColumn(format="%.1f", width="minishort"), "本次叫貨": st.column_config.NumberColumn(format="%.1f", width="minishort"), "期間消耗": st.column_config.NumberColumn(format="%.1f", width="minishort")})
    with t2:
        if not HAS_PLOTLY: st.info("💡 Plotly 未安裝，無法顯示趨勢圖。")
        else:
            col_v_h, col_i_h = st.columns(2)
            all_v_h = sorted(v_df["廠商"].unique().tolist())
            sel_v_h = col_v_h.selectbox("📦 1. 選擇廠商", options=all_v_h, key="h_v_t2")
            v_filtered = v_df[v_df["廠商"] == sel_v_h]
            all_i_h = sorted(v_filtered["品項名稱"].unique().tolist())
            sel_i_h = col_i_h.selectbox("🏷️ 2. 選擇品項", options=all_i_h, key="h_i_t2")
            p_df = v_filtered[v_filtered["品項名稱"] == sel_i_h].copy()
            p_df["日期標記"] = pd.to_datetime(p_df["日期"]).dt.strftime("%Y-%m-%d")
            p_df = p_df.sort_values("日期標記")
            if not p_df.empty:
                fig = px.line(p_df, x="日期標記", y="期間消耗", markers=True, title=f"📈 【{sel_i_h}】消耗趨勢")
                fig.update_layout(xaxis_type="category", hovermode="x unified", xaxis_title="日期")
                st.plotly_chart(fig, use_container_width=True)
    if st.button("⬅️ 返回", use_container_width=True, key="back_hist_final"):
        st.session_state.step = "select_vendor"; st.rerun()

# ============================================================
# [E5] export - 今日進貨明細輸出
# ============================================================
def page_export():
    st.title("📋 今日進貨明細")
    hist_df = get_cloud_data()
    week_map = {0: "一", 1: "二", 2: "三", 3: "四", 4: "五", 5: "六", 6: "日"}
    delivery_date = st.session_state.record_date + timedelta(days=1)
    header_date = f"{delivery_date.month}/{delivery_date.day}({week_map[delivery_date.weekday()]})"
    if not hist_df.empty:
        recs = hist_df[(hist_df["店名"] == st.session_state.store) & (hist_df["日期"].astype(str) == str(st.session_state.record_date)) & (hist_df["本次叫貨"] > 0)]
        if not recs.empty:
            output = f"【{st.session_state.store}】\n{header_date}\n"
            for v in recs["廠商"].unique():
                output += f"\n{v}\n{st.session_state.store}\n"
                for _, r in recs[recs["廠商"] == v].iterrows():
                    val = float(r["本次叫貨"])
                    val_s = int(val) if val.is_integer() else val
                    output += f"{r['品項名稱']} {val_s} {r['單位']}\n"
                output += f"禮拜{week_map[delivery_date.weekday()]}到，謝謝\n"
            st.text_area("📱 LINE 訊息內容預覽", value=output, height=350)
            if st.button("🚀 直接發送明細至 LINE", type="primary", use_container_width=True):
