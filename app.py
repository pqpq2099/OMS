# =====================================================
# OMS SYSTEM MAP (TOC)
# =====================================================
# [A0] Imports
# [A1] Config
# [A2] Global UI Style
# [B1] Google Sheets IO
# [B2] LINE Messaging
# [C1] CSV Loader
# [D1] Shared Tools
# [E1] select_store - 分店選擇頁
# [E2] select_vendor - 廠商與功能中心
# [E3] fill_items - 盤點輸入 / 叫貨核心
# [E4] view_history - 歷史紀錄查詢
# [E5] export - 今日進貨明細輸出
# [E6] analysis - 進銷存分析中心
# [F1] Router
# [G1] Main
# =====================================================


# ============================================================
# [A0] Imports
# ============================================================
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
from pathlib import Path
import plotly.express as px
HAS_PLOTLY = True

# ============================================================
# [A1] Config - 你最常改的地方都放這裡
# ============================================================
SHEET_ID = "1c9twPCyOumPKSau5xgUShJJAG-D9aaZBhK2FWBl2zwc"

CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv")
CSV_STORE = Path("品項總覽.xlsx - 分店.csv")
CSV_PRICE = Path("品項總覽.xlsx - 價格歷史.csv")  # ⭐價格歷史（可沒有）


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
    """讀取特定工作表數據（雲端）"""
    try:
        client = get_gspread_client()
        if not client:
            return pd.DataFrame()

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
    if not client:
        return False
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
    import requests
    import json

    try:
        token = st.secrets["line_bot"]["channel_access_token"]
        current_store = st.session_state.get("store", "")
        target_id = st.secrets.get("line_groups", {}).get(current_store)

        if not target_id:
            target_id = st.secrets["line_bot"].get("user_id")

        if not target_id:
            st.error(f"❌ 找不到【{current_store}】的發送目標 (Group ID)，請檢查 Secrets 設定。")
            return False

        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        payload = {"to": target_id, "messages": [{"type": "text", "text": message}]}

        response = requests.post(url, headers=headers, data=json.dumps(payload))
        return response.status_code == 200
    except Exception as e:
        st.error(f"❌ LINE 推送錯誤: {e}")
        return False


# ============================================================
# [C1] Local Data (CSV) - 讀取品項/分店/價格歷史
# ============================================================
def load_csv_safe(path: Path) -> pd.DataFrame | None:
    for enc in ["utf-8-sig", "utf-8", "cp950", "big5"]:
        try:
            df = pd.read_csv(path, encoding=enc)
            return df.map(lambda x: str(x).strip() if isinstance(x, str) else x)
        except Exception:
            continue
    return None


def get_price_by_date(item_id: str, target_date: date, price_df: pd.DataFrame | None) -> float:
    """
    價格歷史規則：
      生效日 <= target_date
      且 (結束日為空 OR target_date <= 結束日)
    找不到回傳 0.0
    """
    if price_df is None or price_df.empty:
        return 0.0

    df = price_df.copy()

    # 欄位防呆：至少要有 品項ID / 單價 / 生效日
    required = {"品項ID", "單價", "生效日"}
    if not required.issubset(set(df.columns)):
        return 0.0

    # 結束日允許沒有
    if "結束日" not in df.columns:
        df["結束日"] = pd.NaT

    # 型別整理
    df["品項ID"] = df["品項ID"].astype(str).str.strip()
    df["單價"] = pd.to_numeric(df["單價"], errors="coerce").fillna(0)

    df["生效日"] = pd.to_datetime(df["生效日"], errors="coerce")
    df["結束日"] = pd.to_datetime(df["結束日"], errors="coerce")

    target_ts = pd.Timestamp(target_date)
    item_id = str(item_id).strip()

    matched = df[
        (df["品項ID"] == item_id)
        & (df["生效日"].notna())
        & (df["生效日"] <= target_ts)
        & (df["結束日"].isna() | (df["結束日"] >= target_ts))
    ].sort_values("生效日")

    if matched.empty:
        return 0.0

    return float(matched.iloc[-1]["單價"])

def load_master_data():
    df_s = load_csv_safe(CSV_STORE)
    df_i = load_csv_safe(CSV_ITEMS)
    df_pr = load_csv_safe(CSV_PRICE)

    item_display_map = {}
    if df_i is not None and not df_i.empty and "品項ID" in df_i.columns and "品項名稱" in df_i.columns:
        item_display_map = df_i.drop_duplicates("品項ID").set_index("品項ID")["品項名稱"].to_dict()

    return df_s, df_i, df_pr, item_display_map


# ============================================================
# [D1] Session State Init
# ============================================================
def init_session():
    if "step" not in st.session_state:
        st.session_state.step = "select_store"
    if "record_date" not in st.session_state:
        st.session_state.record_date = date.today()


# ============================================================
# [E1] select_store - 分店選擇頁
# ============================================================
def page_select_store(df_s: pd.DataFrame | None):
    st.markdown("<style>.block-container { padding-top: 4rem !important; }</style>", unsafe_allow_html=True)
    st.title("🏠 選擇分店")

    if df_s is None or df_s.empty or "分店名稱" not in df_s.columns:
        st.warning("⚠️ 分店資料讀取失敗或缺少欄位：分店名稱")
        return

for s in df_s["分店名稱"].unique():
    if st.button(f"📍 {s}", key=f"s_{s}", use_container_width=True):
        st.session_state.store = s
        st.session_state.step = "select_vendor"
        st.rerun()
# ============================================================
# [E2] select_vendor - 廠商與功能中心
# ============================================================

def page_select_vendor(df_i: pd.DataFrame | None):
    st.markdown("<style>.block-container { padding-top: 4rem !important; }</style>", unsafe_allow_html=True)
    st.title(f"🏢 {st.session_state.store}")
    st.session_state.record_date = st.date_input("🗓️ 盤點日期", value=st.session_state.record_date)

    # 廠商按鈕
    if df_i is None or df_i.empty or "廠商名稱" not in df_i.columns:
        st.warning("⚠️ 品項資料讀取失敗或缺少欄位：廠商名稱")
    else:
        vendors = sorted(df_i["廠商名稱"].unique())
        for i in range(0, len(vendors), 2):
            cols = st.columns(2)

            with cols[0]:
                v_left = vendors[i]
                if st.(f"📦 {v_left}", key=f"v_{v_left}", use_container_width=True):
                    st.session_state.vendor = v_left
                    st.session_state.history_df = get_cloud_data()
                    st.session_state.step = "fill_items"
                    st.rerun()

            if i + 1 < len(vendors):
                with cols[1]:
                    v_right = vendors[i + 1]
                    if st.(f"📦 {v_right}", key=f"v_{v_right}", use_container_width=True):
                        st.session_state.vendor = v_right
                        st.session_state.history_df = get_cloud_data()
                        st.session_state.step = "fill_items"
                        st.rerun()

# 功能中心
st.write("<b>📊 報表與分析中心</b>", unsafe_allow_html=True)

if st.button("📄 產生今日進貨明細", type="primary", use_container_width=True):
    st.session_state.history_df = get_cloud_data()
    st.session_state.step = "export"
    st.rerun()

if st.button("📈 期間進銷存分析", use_container_width=True):
    st.session_state.history_df = get_cloud_data()
    st.session_state.step = "analysis"
    st.rerun()

history_sheet = f"{st.session_state.store}_紀錄"
if st.button("📜 查看分店歷史紀錄", use_container_width=True):
    st.session_state.view_df = get_worksheet_data(history_sheet)
    st.session_state.step = "view_history"
    st.rerun()

if st.button("⬅️ 返回分店列表", use_container_width=True):
    st.session_state.step = "select_store"
    st.rerun()
        
# ============================================================
# [E3] fill_items - 盤點輸入 / 叫貨核心
# ============================================================

def page_fill_items(df_i: pd.DataFrame | None, df_pr: pd.DataFrame | None, item_display_map: dict):
    # 單排鎖定 CSS
    st.markdown(
        """
        <style>
        .block-container { padding-top: 2rem !important; padding-left: 0.3rem !important; padding-right: 0.3rem !important; }
        [data-testid="stHorizontalBlock"] { display: flex !important; flex-flow: row nowrap !important; align-items: center !important; }
        div[data-testid="stHorizontalBlock"] > div:nth-child(1) { flex: 1 1 auto !important; min-width: 0px !important; }
        div[data-testid="stHorizontalBlock"] > div:nth-child(2),
        div[data-testid="stHorizontalBlock"] > div:nth-child(3) { flex: 0 0 72px !important; min-width: 72px !important; max-width: 72px !important; }
        div[data-testid="stNumberInput"] label { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title(f"📝 {st.session_state.vendor}")

    if df_i is None or df_i.empty:
        st.error("❌ 品項資料未載入，無法盤點")
        return

    items = df_i[df_i["廠商名稱"] == st.session_state.vendor]
    hist_df = st.session_state.get("history_df", pd.DataFrame())

    # 上次參考表
    if not hist_df.empty:
        ref_list = []
        for f_id in items["品項ID"].unique():
            f_name = item_display_map.get(f_id, "")

            past = hist_df[
                (hist_df["店名"].astype(str).str.strip() == str(st.session_state.store).strip())
                & (
                    (hist_df["品項ID"].astype(str).str.strip() == str(f_id).strip())
                    | (hist_df["品項名稱"].astype(str).str.strip() == str(f_name).strip())
                )
            ]

            if not past.empty:
                latest = past.iloc[-1]
                p_p_val = pd.to_numeric(latest.get("本次叫貨", 0), errors="coerce")
                p_u_val = pd.to_numeric(latest.get("期間消耗", 0), errors="coerce")
                if p_p_val > 0 or p_u_val > 0:
                    ref_list.append({"品項名稱": f_name, "上次叫貨": round(float(p_p_val), 1), "期間消耗": round(float(p_u_val), 1)})

        if ref_list:
            with st.expander("📊 查看上次叫貨/消耗參考 (已自動隱藏無紀錄品項)", expanded=False):
                display_ref_df = pd.DataFrame(ref_list)
                for col in ["上次叫貨", "期間消耗"]:
                    display_ref_df[col] = display_ref_df[col].apply(lambda x: f"{x:.1f}")
                st.table(display_ref_df)

    st.write("---")
    h1, h2, h3 = st.columns([6, 1, 1])
    h1.write("<b>品項名稱</b>", unsafe_allow_html=True)
    h2.write("<div style='text-align:center;'><b>庫存</b></div>", unsafe_allow_html=True)
    h3.write("<div style='text-align:center;'><b>進貨</b></div>", unsafe_allow_html=True)

    with st.form("inventory_form"):
        temp_data = []
        last_item_display_name = ""

        for _, row in items.iterrows():
            f_id = str(row["品項ID"]).strip()
            d_n = str(row["品項名稱"]).strip()
            unit = str(row["單位"]).strip()

            # ✅ 價格：先用價格歷史（依盤點日期），找不到就用品項檔單價
            default_price = pd.to_numeric(row.get("單價", 0), errors="coerce")
            price = get_price_by_date(f_id, st.session_state.record_date, df_pr) or float(default_price)

            # 建議叫貨（原邏輯保留）
            p_s, p_p = 0.0, 0.0
            avg_usage = 0.0
            suggest_qty = 0.0

            if not hist_df.empty:
                past = hist_df[
                    (hist_df["店名"].astype(str).str.strip() == str(st.session_state.store).strip())
                    & (
                        (hist_df["品項ID"].astype(str).str.strip() == str(f_id).strip())
                        | (hist_df["品項名稱"].astype(str).str.strip() == str(d_n).strip())
                    )
                ].copy()

                if not past.empty:
                    latest = past.iloc[-1]
                    p_s = float(latest.get("本次剩餘", 0.0))
                    p_p = float(latest.get("本次叫貨", 0.0))
                    recent_usage = past["期間消耗"].tail(3).astype(float)
                    avg_usage = recent_usage.mean() if not recent_usage.empty else 0.0
                    suggest_qty = max(0.0, (avg_usage * 1.5) - p_s)

            c1, c2, c3 = st.columns([6, 1, 1])
            with c1:
                if d_n == last_item_display_name:
                    st.write(f"<span style='color:gray;'>└ </span> <b>{unit}</b>", unsafe_allow_html=True)
                else:
                    st.write(f"<b>{d_n}</b>", unsafe_allow_html=True)

                # 你要的資訊集中顯示在 caption
                st.caption(f"{unit} (前結:{p_s:.1f} | 單價:{price:.1f} | 💡建議:{suggest_qty:.1f})")
                last_item_display_name = d_n

            with c2:
                t_s = st.number_input("庫", min_value=0.0, step=0.1, key=f"s_{f_id}", format="%g", value=None, label_visibility="collapsed")
            with c3:
                t_p = st.number_input("進", min_value=0.0, step=0.1, key=f"p_{f_id}", format="%g", value=None, label_visibility="collapsed")

            # 計算與封裝（原邏輯保留）
            t_s_v = t_s if t_s is not None else 0.0
            t_p_v = t_p if t_p is not None else 0.0
            usage = p_s - t_s_v

            temp_data.append([
                str(st.session_state.record_date), st.session_state.store, st.session_state.vendor,
                f_id, d_n, unit, p_s, p_p, t_s_v, t_p_v, usage, float(price), float(round(t_p_v * price, 1))
            ])

        # 儲存（保留你原本的判斷）
        if st.form_submit_button("💾 儲存並同步數據", use_container_width=True):
            valid = [d for d in temp_data if d[8] >= 0 or d[9] > 0]  # 原封不動（你之後要優化我再幫你改）
            if valid and sync_to_cloud(pd.DataFrame(valid)):
                st.success("✅ 儲存成功")
                st.session_state.step = "select_vendor"
                st.rerun()

    st.("⬅️ 返回功能選單", on_click=lambda: st.session_state.update(step="select_vendor"), use_container_width=True, key="back_from_fill")

# ============================================================
# [E4] view_history - 歷史紀錄查詢
# ============================================================

def page_view_history():
    st.markdown(
        """
        <style>
        [data-testid="stMainBlockContainer"] { max-width: 95% !important; padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
        [data-testid="stDataFrame"] [role="gridcell"] { padding: 1px 2px !important; line-height: 1.0 !important; }
        [data-testid="stDataFrame"] [role="columnheader"] { padding: 2px 2px !important; font-size: 10px !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title(f"📜 {st.session_state.store} 歷史庫")
    v_df = st.session_state.get("view_df", pd.DataFrame())

    if v_df.empty:
        st.info("💡 尚無歷史紀錄可供查看。")
        st.("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"), use_container_width=True)
        return

    c_h_date1, c_h_date2 = st.columns(2)
    h_start = c_h_date1.date_input("起始日期", value=date.today() - timedelta(7), key="h_start")
    h_end = c_h_date2.date_input("結束日期", value=date.today(), key="h_end")

    t1, t2 = st.tabs(["📋 明細", "📈 趨勢"])

    with t1:
        v_df["日期_dt"] = pd.to_datetime(v_df["日期"]).dt.date
        temp_filt = v_df[(v_df["日期_dt"] >= h_start) & (v_df["日期_dt"] <= h_end)].copy()

        if temp_filt.empty:
            st.info("💡 此區間內無紀錄。")
        else:
            col_v, col_i = st.columns(2)
            all_v_m = ["全部廠商"] + sorted(temp_filt["廠商"].unique().tolist())
            sel_v_m = col_v.selectbox("📦 1. 選擇廠商", options=all_v_m, index=0, key="h_v_m_sel")

            f_df = temp_filt.copy()
            if sel_v_m != "全部廠商":
                f_df = f_df[f_df["廠商"] == sel_v_m]

            all_i_m = ["全部品項"] + sorted(f_df["品項名稱"].unique().tolist())
            sel_i_m = col_i.selectbox("🏷️ 2. 選擇品項", options=all_i_m, index=0, key="h_i_m_sel")

            if sel_i_m != "全部品項":
                f_df = f_df[f_df["品項名稱"] == sel_i_m]

            if "日期" in f_df.columns:
                f_df["顯示日期"] = pd.to_datetime(f_df["日期"]).dt.strftime("%m-%d")

            cols_order = ["顯示日期", "廠商", "品項名稱", "單位", "上次剩餘", "上次叫貨", "本次剩餘", "本次叫貨", "期間消耗"]
            final_cols = [c for c in cols_order if c in f_df.columns]

            st.dataframe(
                f_df[final_cols].sort_values("顯示日期", ascending=False),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "顯示日期": st.column_config.TextColumn("日期", width="minishort"),
                    "廠商": st.column_config.TextColumn(width="small"),
                    "品項名稱": st.column_config.TextColumn(width="medium"),
                    "單位": st.column_config.TextColumn(width="minishort"),
                    "上次剩餘": st.column_config.NumberColumn(format="%.1f", width="minishort"),
                    "上次叫貨": st.column_config.NumberColumn(format="%.1f", width="minishort"),
                    "本次剩餘": st.column_config.NumberColumn(format="%.1f", width="minishort"),
                    "本次叫貨": st.column_config.NumberColumn(format="%.1f", width="minishort"),
                    "期間消耗": st.column_config.NumberColumn(format="%.1f", width="minishort"),
                },
            )

    with t2:
        if not HAS_PLOTLY:
            st.info("💡 Plotly 未安裝，無法顯示趨勢圖。")
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

    st.("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"), use_container_width=True, key="back_hist_final")

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
        recs = hist_df[
            (hist_df["店名"] == st.session_state.store)
            & (hist_df["日期"].astype(str) == str(st.session_state.record_date))
            & (hist_df["本次叫貨"] > 0)
        ]

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

            if st.("🚀 直接發送明細至 LINE", type="primary", use_container_width=True):
                if send_line_message(output):
                    st.success(f"✅ 已成功推送到【{st.session_state.store}】群組！")
                else:
                    st.error("❌ 發送失敗，請檢查該店 ID 已填入 Secrets 且機器人在群組內。")
        else:
            st.info("💡 今日尚無叫貨紀錄。")

    st.button("⬅️ 返回選單", on_click=lambda: st.session_state.update(step="select_vendor"), use_container_width=True, key="back_to_vendor_export")

# ============================================================
# [E6] analysis - 進銷存分析中心（含圖表）
# ============================================================
def page_analysis():
    st.title("📊 進銷存分析")

    # ============================================================
    # [E6.1] Load Data + Date Range
    # ============================================================
    a_df = get_worksheet_data("Records")
    c_date1, c_date2 = st.columns(2)
    start = c_date1.date_input("起始日期", value=date.today() - timedelta(14), key="ana_start")
    end = c_date2.date_input("結束日期", value=date.today(), key="ana_end")

    if a_df.empty:
        st.error("❌ 無法從 Google Sheets 讀取 Records 資料。")
        st.("⬅️ 返回選單", on_click=lambda: st.session_state.update(step="select_vendor"), use_container_width=True)
        return

    # ============================================================
    # [E6.2] Clean + Filter by Store + Date
    # ============================================================
    a_df["日期"] = pd.to_datetime(a_df["日期"], errors="coerce").dt.date
    current_store = str(st.session_state.store).strip()

    filt = a_df[
        (a_df["店名"].astype(str).str.strip() == current_store)
        & (a_df["日期"] >= start)
        & (a_df["日期"] <= end)
    ].copy()

    if filt.empty:
        st.warning(f"⚠️ 在 {start} 到 {end} 之間查無紀錄。")
        st.("⬅️ 返回選單", on_click=lambda: st.session_state.update(step="select_vendor"), use_container_width=True)
        return

    # ============================================================
    # [E6.3] Vendor / Item Dropdown Filters
    # ============================================================
    st.markdown("---")
    col_v, col_i = st.columns(2)

    all_v = ["全部廠商"] + sorted(filt["廠商"].dropna().unique().tolist())
    selected_v = col_v.selectbox("📦 1. 選擇廠商", options=all_v, index=0, key="ana_v_box")

    v_filt = filt.copy()
    if selected_v != "全部廠商":
        v_filt = v_filt[v_filt["廠商"] == selected_v]

    all_i = ["全部品項"] + sorted(v_filt["品項名稱"].dropna().unique().tolist())
    selected_item = col_i.selectbox("🏷️ 2. 選擇品項", options=all_i, index=0, key="ana_i_box")

    final_filt = v_filt.copy()
    if selected_item != "全部品項":
        final_filt = final_filt[final_filt["品項名稱"] == selected_item]

    # ============================================================
    # [E6.4] Summary Cards
    # ============================================================
    total_buy = final_filt["總金額"].sum() if "總金額" in final_filt.columns else 0
    last_stock = final_filt.sort_values("日期").groupby("品項名稱").tail(1)
    total_stock_value = (
        (last_stock["本次剩餘"] * last_stock["單價"]).sum()
        if ("本次剩餘" in last_stock.columns and "單價" in last_stock.columns)
        else 0
    )

    st.markdown(
        f"""
        <div style='display: flex; gap: 10px; margin-bottom: 20px;'>
            <div style='flex: 1; padding: 10px; border-radius: 8px; border-left: 4px solid #4A90E2; background: rgba(74, 144, 226, 0.05);'>
                <div style='font-size: 11px; font-weight: 700; opacity: 0.8;'>💰 採購總額 ({selected_v})</div>
                <div style='font-size: 18px; font-weight: 800; color: #4A90E2;'>${total_buy:,.1f}</div>
            </div>
            <div style='flex: 1; padding: 10px; border-radius: 8px; border-left: 4px solid #50C878; background: rgba(80, 200, 120, 0.05);'>
                <div style='font-size: 11px; font-weight: 700; opacity: 0.8;'>📦 庫存殘值估計</div>
                <div style='font-size: 18px; font-weight: 800; color: #50C878;'>${total_stock_value:,.1f}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ============================================================
    # 確保 final_filt 一定存在
    # ============================================================
    if final_filt is None or len(final_filt) == 0:
        st.info("💡 尚未產生分析資料")
        return

    # ============================================================
    # [E6.5] Tabs - 明細 / 趨勢
    # ============================================================
    t_detail, t_trend = st.tabs(["📋 明細", "📈 趨勢"])

    # ----------------------------
    # 明細（只表格）
    # ----------------------------
    with t_detail:
        st.write("<b>📋 進銷存匯總明細</b>", unsafe_allow_html=True)

        required_cols = {"廠商", "品項名稱", "單位", "單價", "期間消耗", "本次叫貨", "總金額"}

        if not required_cols.issubset(set(final_filt.columns)):
            st.warning("⚠️ Records 欄位不足")
        else:
            summ_df = (
                final_filt.groupby(["廠商", "品項名稱", "單位", "單價"])
                .agg({"期間消耗": "sum", "本次叫貨": "sum", "總金額": "sum"})
                .reset_index()
            )

            st.dataframe(
                summ_df.sort_values("總金額", ascending=False),
                use_container_width=True,
                hide_index=True,
            )

    # ----------------------------
    # 趨勢（Plotly）
    # ----------------------------
    with t_trend:
        st.write("<b>📈 採購金額圖表</b>", unsafe_allow_html=True)

        PLOTLY_CONFIG = {
            "displayModeBar": True,
            "displaylogo": False,
            "scrollZoom": False,
            "doubleClick": False,
            "modeBarsToRemove": [
                "zoom2d","pan2d","select2d","lasso2d",
                "zoomIn2d","zoomOut2d",
                "autoScale2d","resetScale2d",
                "hoverClosestCartesian",
                "hoverCompareCartesian",
                "toggleSpikelines"
            ],
        }

        if HAS_PLOTLY:

            # 趨勢圖
            if {"日期","總金額"}.issubset(final_filt.columns):
                trend_df = final_filt.copy()
                trend_df["日期_dt"] = pd.to_datetime(trend_df["日期"], errors="coerce")

                trend_daily = (
                    trend_df.dropna(subset=["日期_dt"])
                    .groupby("日期_dt", as_index=False)["總金額"]
                    .sum()
                    .sort_values("日期_dt")
                )

                if not trend_daily.empty:
                    fig1 = px.line(
                        trend_daily,
                        x="日期_dt",
                        y="總金額",
                        markers=True,
                        title="📈 採購金額趨勢（依日期）"
                    )
                    fig1.update_layout(dragmode=False)
                    st.plotly_chart(fig1, use_container_width=True, config=PLOTLY_CONFIG)

            # Top20
            if {"品項名稱","總金額"}.issubset(final_filt.columns):
                rank_df = (
                    final_filt.groupby("品項名稱", as_index=False)["總金額"]
                    .sum()
                    .sort_values("總金額", ascending=False)
                    .head(20)
                )

                if not rank_df.empty:
                    fig2 = px.bar(rank_df, x="品項名稱", y="總金額",
                                  title="📊 品項採購金額排行（Top 20）")
                    fig2.update_layout(dragmode=False)
                    st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)

        else:
            st.info("💡 Plotly 未啟用")

        st.divider()

        st.warning("DEBUG: reached bottom of t_trend")  # 這行一定會出現
        st.divider()
if st.button("⬅️ 返回選單", use_container_width=True, key="back_from_analysis"):
    st.session_state.step = "select_vendor"
    st.rerun()
# ============================================================
# [F1] Router - 不改你原本 step 架構，只是集中管理
# ============================================================
def router(df_s, df_i, df_pr, item_display_map):
    step = st.session_state.step

    if step == "select_store":
        page_select_store(df_s)

    elif step == "select_vendor":
        page_select_vendor(df_i)

    elif step == "fill_items":
        page_fill_items(df_i, df_pr, item_display_map)

    elif step == "view_history":
        page_view_history()

    elif step == "export":
        page_export()

    elif step == "analysis":
        page_analysis()

    else:
        st.session_state.step = "select_store"
        st.rerun()


# ============================================================
# [G1] Main - 程式入口
# ============================================================
def main():
    apply_global_style()
    init_session()

    df_s, df_i, df_pr, item_display_map = load_master_data()
    router(df_s, df_i, df_pr, item_display_map)


if __name__ == "__main__":
    main()



