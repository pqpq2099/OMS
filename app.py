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
    except: # 💡 這裡之前遺失了縮排與對應，導致 SyntaxError
        return False

# 💡 戰略升級：多群組自動對位發送系統
def send_line_message(message):
    import requests
    import json
    try:
        # 1. 抓取通訊密鑰
        token = st.secrets["line_bot"]["channel_access_token"]
        
        # 2. 核心對位：抓取當前分店名稱
        current_store = st.session_state.get('store', '')
        
        # 3. 從 [line_groups] 表格中檢索對應 ID (支援你剛設的 "師大店" 等)
        # 如果找不到對應 ID，則嘗試回退到 user_id (個人) 作為保險
        target_id = st.secrets.get("line_groups", {}).get(current_store)
        
        if not target_id:
            # 如果群組表找不到，才考慮發給個人，或報錯
            target_id = st.secrets["line_bot"].get("user_id")
            
        if not target_id:
            st.error(f"❌ 找不到【{current_store}】的發送目標 (Group ID)，請檢查 Secrets 設定。")
            return False
        
        url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        payload = {
            "to": target_id,
            "messages": [{"type": "text", "text": message}]
        }
        
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        return response.status_code == 200
    except Exception as e:
        st.error(f"❌ LINE 推送錯誤: {e}")
        return False
# =========================
# 2. 全域視覺標準
# =========================
# =========================
# 2. 全域視覺標準
# =========================
st.set_page_config(page_title="OMS 系統", layout="centered")
st.markdown("""
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

    /* 3. 表頭文字：稍微加重結構感，但不強制背景色以避免看不見字 */
    [data-testid="stTable"] th,
    [data-testid="stDataFrame"] [role="columnheader"] {
        font-weight: 600 !important;
    }

    /* 4. 移除數字框內建按鈕與外距 (維持原本的物理鎖定) */
    div[data-testid="stNumberInputStepUp"], 
    div[data-testid="stNumberInputStepDown"] { display: none !important; }
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
    
# --- 💡 廠商按鈕：兩列並排戰略 (已修正邏輯衝突) ---
    if df_i is not None:
        vendors = sorted(df_i['廠商名稱'].unique())
        
        # 使用每列 2 個的柵格邏輯
        for i in range(0, len(vendors), 2):
            cols = st.columns(2)  # 建立兩列
            
            # 1. 處理左側按鈕
            with cols[0]:
                v_left = vendors[i]
                if st.button(f"📦 {v_left}", key=f"v_{v_left}", use_container_width=True):
                    st.session_state.vendor = v_left
                    st.session_state.history_df = get_cloud_data()
                    st.session_state.step = "fill_items"
                    st.rerun()
            
            # 2. 處理右側按鈕 (需判斷是否還有下一個廠商)
            if i + 1 < len(vendors):
                with cols[1]:
                    v_right = vendors[i+1]
                    if st.button(f"📦 {v_right}", key=f"v_{v_right}", use_container_width=True):
                        st.session_state.vendor = v_right
                        st.session_state.history_df = get_cloud_data()
                        st.session_state.step = "fill_items"
                        st.rerun()
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
    # 💡 物理單排鎖定 CSS
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
    
    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    hist_df = st.session_state.get('history_df', pd.DataFrame())
    
# --- 💡 庫存頁面：上次數據參考 (完整覆蓋：加入自動過濾邏輯) ---
    if not hist_df.empty:
        ref_list = []
        for f_id in items['品項ID'].unique():
            f_name = item_display_map.get(f_id, "")
            
            # 1. 執行嚴格對位過濾
            past = hist_df[
                (hist_df['店名'].astype(str).str.strip() == str(st.session_state.store).strip()) & 
                ((hist_df['品項ID'].astype(str).str.strip() == str(f_id).strip()) | 
                 (hist_df['品項名稱'].astype(str).str.strip() == str(f_name).strip()))
            ]
            
            # 2. 🚀 戰略過濾：只有「歷史上有紀錄」且「數值不為0」的才加入表格
            if not past.empty:
                latest = past.iloc[-1]
                p_p_val = pd.to_numeric(latest.get('本次叫貨', 0), errors='coerce')
                p_u_val = pd.to_numeric(latest.get('期間消耗', 0), errors='coerce')
                
                # 只有當真的有叫貨或消耗過，才顯示在參考清單中
                if p_p_val > 0 or p_u_val > 0:
                    ref_list.append({
                        "品項名稱": f_name, 
                        "上次叫貨": round(float(p_p_val), 1), 
                        "期間消耗": round(float(p_u_val), 1)
                    })
        
        # 3. 介面呈現
        if ref_list:
            with st.expander("📊 查看上次叫貨/消耗參考 (已自動隱藏無紀錄品項)", expanded=False):
                display_ref_df = pd.DataFrame(ref_list)
                for col in ["上次叫貨", "期間消耗"]:
                    display_ref_df[col] = display_ref_df[col].apply(lambda x: f"{x:.1f}")
                st.table(display_ref_df)

    st.write("---")
    # 💡 這裡就是您報錯的地方，現在已經精確對齊
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
            
# --- 🚀 戰略強化：智慧建議叫貨與數據歸位邏輯 ---
            p_s, p_p = 0.0, 0.0
            avg_usage = 0.0
            suggest_qty = 0.0
            
            if not hist_df.empty:
                # 1. 精確對位：抓取該店該品項的歷史紀錄
                past = hist_df[
                    (hist_df['店名'].astype(str).str.strip() == str(st.session_state.store).strip()) & 
                    ((hist_df['品項ID'].astype(str).str.strip() == str(f_id).strip()) | 
                     (hist_df['品項名稱'].astype(str).str.strip() == str(d_n).strip()))
                ].copy()
                
                if not past.empty:
                    latest = past.iloc[-1]
                    p_s = float(latest.get('本次剩餘', 0.0))
                    p_p = float(latest.get('本次叫貨', 0.0))
                    
                    # 💡 智慧算法：取最近 3 筆消耗算日均值
                    recent_usage = past['期間消耗'].tail(3).astype(float)
                    avg_usage = recent_usage.mean() if not recent_usage.empty else 0.0
                    
                    # 💡 建議叫貨公式：(日均消耗 * 1.5倍安全量) - 當前剩餘
                    suggest_qty = max(0.0, (avg_usage * 1.5) - p_s)
            # -----------------------------------------------
            
            c1, c2, c3 = st.columns([6, 1, 1])
            with c1:
                if d_n == last_item_display_name:
                    st.write(f"<span style='color:gray;'>└ </span> <b>{unit}</b>", unsafe_allow_html=True)
                else:
                    st.write(f"<b>{d_n}</b>", unsafe_allow_html=True)
                
                p_sum = p_s + p_p; p_show = round(p_sum, 1)
                # 💡 視覺強化：除了前結，多顯示建議叫貨量
                st.caption(f"{unit} (前結:{p_s:.1f} | 💡 建議:{suggest_qty:.1f})")
                last_item_display_name = d_n
            
            with c2:
                t_s = st.number_input("庫", min_value=0.0, step=0.1, key=f"s_{f_id}", format="%g", value=None, label_visibility="collapsed")
            with c3:
                t_p = st.number_input("進", min_value=0.0, step=0.1, key=f"p_{f_id}", format="%g", value=None, label_visibility="collapsed")
            
# --- 核心計算與數據封裝 ---
            t_s_v = t_s if t_s is not None else 0.0
            t_p_v = t_p if t_p is not None else 0.0
            usage = p_s - t_s_v  # 💡 戰略修正：消耗 = 上次結餘 - 本次庫存
            
            temp_data.append([
                str(st.session_state.record_date), st.session_state.store, st.session_state.vendor, 
                f_id, d_n, unit, p_s, p_p, t_s_v, t_p_v, usage, float(price), float(round(t_p_v * price, 1))
            ])

        # --- 儲存觸發區 (必須在 for 迴圈外，但在 form 之內) ---
        if st.form_submit_button("💾 儲存並同步數據", use_container_width=True):
            # 💡 戰略強化：放寬門檻，只要「有填寫庫存(不為None)」或「有進貨」就存檔，確保數據鏈連續
            valid = [d for d in temp_data if d[8] >= 0 or d[9] > 0]
            
            if valid and sync_to_cloud(pd.DataFrame(valid)):
                st.success("✅ 儲存成功")
                st.session_state.step = "select_vendor"
                st.rerun()
                
    # --- 導覽區 (必須在 form 之外) ---
    st.button("⬅️ 返回功能選單", on_click=lambda: st.session_state.update(step="select_vendor"), use_container_width=True, key="back_from_fill")
    
# --- 歷史紀錄 (全覽優先 + 日期置前版) ---
elif st.session_state.step == "view_history":
    st.markdown("""
        <style>
            [data-testid="stMainBlockContainer"] { max-width: 95% !important; padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
            [data-testid="stDataFrame"] [role="gridcell"] { padding: 1px 2px !important; line-height: 1.0 !important; }
            [data-testid="stDataFrame"] [role="columnheader"] { padding: 2px 2px !important; font-size: 10px !important; }
        </style>
    """, unsafe_allow_html=True)
    
    st.title(f"📜 {st.session_state.store} 歷史庫")
    v_df = st.session_state.get('view_df', pd.DataFrame())
    
    if not v_df.empty:
        # 1. 建立日期篩選
        c_h_date1, c_h_date2 = st.columns(2)
        h_start = c_h_date1.date_input("起始日期", value=date.today()-timedelta(7), key="h_start")
        h_end = c_h_date2.date_input("結束日期", value=date.today(), key="h_end")

        t1, t2 = st.tabs(["📋 明細", "📈 趨勢"])
        
        with t1:
            # A. 數據清洗與時間過濾
            v_df['日期_dt'] = pd.to_datetime(v_df['日期']).dt.date
            temp_filt = v_df[(v_df['日期_dt'] >= h_start) & (v_df['日期_dt'] <= h_end)].copy()
            
            if not temp_filt.empty:
                col_v, col_i = st.columns(2)
                
                # 💡 戰略要求 1：預設全部廠商
                all_v_m = ["全部廠商"] + sorted(temp_filt['廠商'].unique().tolist())
                sel_v_m = col_v.selectbox("📦 1. 選擇廠商", options=all_v_m, index=0, key="h_v_m_sel")
                
                # 💡 戰略要求 1：預設全部品項 (建立連動)
                f_df = temp_filt.copy()
                if sel_v_m != "全部廠商":
                    f_df = f_df[f_df['廠商'] == sel_v_m]
                
                all_i_m = ["全部品項"] + sorted(f_df['品項名稱'].unique().tolist())
                sel_i_m = col_i.selectbox("🏷️ 2. 選擇品項", options=all_i_m, index=0, key="h_i_m_sel")
                
                if sel_i_m != "全部品項":
                    f_df = f_df[f_df['品項名稱'] == sel_i_m]

                # 💡 戰略要求 2：日期格式化 (只顯示月日) 並置於首位
                if '日期' in f_df.columns:
                    # 先將日期轉為月-日字串，並新增一欄「顯示日期」
                    f_df['顯示日期'] = pd.to_datetime(f_df['日期']).dt.strftime('%m-%d')
                
                # 重新定義顯示欄位順序：顯示日期置於第一個
                cols_order = ['顯示日期', '廠商', '品項名稱', '單位', '上次剩餘', '上次叫貨', '本次剩餘', '本次叫貨', '期間消耗']
                # 只選取存在的欄位
                final_cols = [c for c in cols_order if c in f_df.columns]
                
                st.dataframe(
                    f_df[final_cols].sort_values('顯示日期', ascending=False), 
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
                    }
                )
            else:
                st.info("💡 此區間內無紀錄。")

        with t2:
            if HAS_PLOTLY:
                col_v_h, col_i_h = st.columns(2)
                all_v_h = sorted(v_df['廠商'].unique().tolist())
                sel_v_h = col_v_h.selectbox("📦 1. 選擇廠商", options=all_v_h, key="h_v_t2")
                
                v_filtered = v_df[v_df['廠商'] == sel_v_h]
                all_i_h = sorted(v_filtered['品項名稱'].unique().tolist())
                sel_i_h = col_i_h.selectbox("🏷️ 2. 選擇品項", options=all_i_h, key="h_i_t2")
                
                p_df = v_filtered[v_filtered['品項名稱'] == sel_i_h].copy()
                # 趨勢圖仍保留年份確保排序正確，但顯示可優化
                p_df['日期標記'] = pd.to_datetime(p_df['日期']).dt.strftime('%Y-%m-%d')
                p_df = p_df.sort_values('日期標記')
                
                if not p_df.empty:
                    fig = px.line(p_df, x="日期標記", y="期間消耗", markers=True, title=f"📈 【{sel_i_h}】消耗趨勢")
                    fig.update_layout(xaxis_type='category', hovermode="x unified", xaxis_title="日期")
                    st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("💡 尚無歷史紀錄可供查看。")

    st.button("⬅️ 返回", on_click=lambda: st.session_state.update(step="select_vendor"), use_container_width=True, key="back_hist_final")
    
# --- 今日進貨明細 (強化發送版) ---
# --- 步驟 4：今日進貨明細 (智慧對照版) ---
elif st.session_state.step == "export":
    st.title("📋 今日進貨明細")
    hist_df = get_cloud_data()
    week_map = {0:'一', 1:'二', 2:'三', 3:'四', 4:'五', 5:'六', 6:'日'}
    delivery_date = st.session_state.record_date + timedelta(days=1)
    header_date = f"{delivery_date.month}/{delivery_date.day}({week_map[delivery_date.weekday()]})"
    
    if not hist_df.empty:
        # A. 數據過濾
        recs = hist_df[(hist_df['店名'] == st.session_state.store) & 
                       (hist_df['日期'].astype(str) == str(st.session_state.record_date)) & 
                       (hist_df['本次叫貨'] > 0)]
        
        if not recs.empty:
            # B. 建立純淨版抬頭
            output = f"【{st.session_state.store}】\n" + f"{header_date}\n"
            
            for v in recs['廠商'].unique():
                output += f"\n{v}\n{st.session_state.store}\n"
                for _, r in recs[recs['廠商'] == v].iterrows():
                    val = float(r['本次叫貨'])
                    val_s = int(val) if val.is_integer() else val
                    output += f"{r['品項名稱']} {val_s} {r['單位']}\n"
                output += f"禮拜{week_map[delivery_date.weekday()]}到，謝謝\n"
            
            # C. 顯示預覽
            st.text_area("📱 LINE 訊息內容預覽", value=output, height=350)
            
            # D. 發送按鈕 (這是在 if not recs.empty 之內)
            if st.button("🚀 直接發送明細至 LINE", type="primary", use_container_width=True):
                if send_line_message(output):
                    st.success(f"✅ 已成功推送到【{st.session_state.store}】群組！")
                else:
                    st.error("❌ 發送失敗，請檢查該店 ID 已填入 Secrets 且機器人在群組內。")
        else:
            # 💡 修正點：這個 else 必須跟 if not recs.empty: 完全對齊
            st.info("💡 今日尚無叫貨紀錄。")
            
    # E. 返回按鈕 (這是在 if not hist_df.empty 之外，與 if 對齊)
    st.button("⬅️ 返回選單", on_click=lambda: st.session_state.update(step="select_vendor"), use_container_width=True, key="back_to_vendor_export")
    
# --- 步驟 5：進銷存分析 (回歸財務與表格核心版) ---
elif st.session_state.step == "analysis":
    st.title("📊 進銷存分析")
    
    # 1. 抓取數據與設定日期
    a_df = get_worksheet_data("Records")
    c_date1, c_date2 = st.columns(2)
    start = c_date1.date_input("起始日期", value=date.today()-timedelta(14), key="ana_start")
    end = c_date2.date_input("結束日期", value=date.today(), key="ana_end")
    
    if a_df.empty:
        st.error("❌ 無法從 Google Sheets 讀取 Records 資料。")
    else:
        # A. 數據清洗
        a_df['日期'] = pd.to_datetime(a_df['日期']).dt.date
        current_store = str(st.session_state.store).strip()
        
        # B. 執行過濾 (店名 + 日期)
        filt = a_df[(a_df['店名'].astype(str).str.strip() == current_store) & 
                    (a_df['日期'] >= start) & (a_df['日期'] <= end)].copy()
        
        if filt.empty:
            st.warning(f"⚠️ 在 {start} 到 {end} 之間查無紀錄。")
        else:
            st.markdown("---")
            # C. 戰略核心：連動式篩選 (預設全部廠商)
            col_v, col_i = st.columns(2)
            
            all_v = ["全部廠商"] + sorted(filt['廠商'].unique().tolist())
            selected_v = col_v.selectbox("📦 1. 選擇廠商", options=all_v, index=0, key="ana_v_box")
            
            # 根據廠商過濾數據
            v_filt = filt.copy()
            if selected_v != "全部廠商":
                v_filt = v_filt[v_filt['廠商'] == selected_v]
            
            all_i = ["全部品項"] + sorted(v_filt['品項名稱'].unique().tolist())
            selected_item = col_i.selectbox("🏷️ 2. 選擇品項", options=all_i, index=0, key="ana_i_box")
            
            final_filt = v_filt.copy()
            if selected_item != "全部品項":
                final_filt = final_filt[final_filt['品項名稱'] == selected_item]

            # D. 財務看板回歸 (金額計算核心)
            # 1. 採購總計 = 本次叫貨 * 單價 (Records 裡已有總金額欄位)
            # 2. 庫存殘值 = 本次剩餘 * 單價
            total_buy = final_filt['總金額'].sum()
            # 計算庫存殘值 (取每個品項最後一筆剩餘量)
            last_stock = final_filt.sort_values('日期').groupby('品項名稱').tail(1)
            total_stock_value = (last_stock['本次剩餘'] * last_stock['單價']).sum()

            st.markdown(f"""
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
            """, unsafe_allow_html=True)

            # E. 數據表格回歸 (以表格為分析主體)
            # 匯總該區間內每個品項的數據
            summ_df = final_filt.groupby(['廠商', '品項名稱', '單位', '單價']).agg({
                '期間消耗': 'sum',
                '本次叫貨': 'sum',
                '總金額': 'sum'
            }).reset_index()
            
            # 加上期末庫存欄位
            stock_map = last_stock.set_index('品項名稱')['本次剩餘'].to_dict()
            summ_df['期末庫存'] = summ_df['品項名稱'].map(stock_map).fillna(0)
            
            st.write("<b>📋 進銷存匯總明細</b>", unsafe_allow_html=True)
            st.dataframe(
                summ_df.sort_values('總金額', ascending=False),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "單價": st.column_config.NumberColumn(format="%.1f"),
                    "期間消耗": st.column_config.NumberColumn(format="%.1f"),
                    "本次叫貨": st.column_config.NumberColumn(format="%.1f"),
                    "總金額": st.column_config.NumberColumn("採購金額", format="$%.1f"),
                    "期末庫存": st.column_config.NumberColumn(format="%.1f")
                }
            )

    st.button("⬅️ 返回選單", on_click=lambda: st.session_state.update(step="select_vendor"), use_container_width=True, key="back_ana_v2")







