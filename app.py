import sqlite3
import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import date, timedelta

# =========================
# 1. 檔案與資料庫設定
# =========================
CSV_STORE = Path("品項總覽.xlsx - 分店.csv")
CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv")
DB_PATH = Path("inventory_system.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_name TEXT,
        vendor_name TEXT,
        item_name TEXT,
        last_stock INTEGER DEFAULT 0,
        last_purchase INTEGER DEFAULT 0,
        this_stock INTEGER DEFAULT 0,
        this_purchase INTEGER DEFAULT 0,
        usage_qty INTEGER DEFAULT 0,
        record_date TEXT,
        UNIQUE(record_date, store_name, item_name)
    )""")
    conn.commit()
    conn.close()

def load_csv_safe(path):
    for enc in ['utf-8', 'cp950', 'big5']:
        try:
            df = pd.read_csv(path, encoding=enc)
            return df.map(lambda x: x.strip() if isinstance(x, str) else x)
        except: continue
    return None

def load_data():
    if not CSV_STORE.exists() or not CSV_ITEMS.exists():
        st.error("❌ 找不到 CSV 檔案。")
        return None, None
    return load_csv_safe(CSV_STORE), load_csv_safe(CSV_ITEMS)

def get_previous_data(store, item, current_date_str):
    conn = get_conn()
    row = conn.execute("""
        SELECT this_stock, this_purchase FROM records 
        WHERE store_name = ? AND item_name = ? AND record_date < ?
        ORDER BY record_date DESC, id DESC LIMIT 1
    """, (store, item, current_date_str)).fetchone()
    conn.close()
    return (int(row['this_stock']), int(row['this_purchase'])) if row else (0, 0)

# =========================
# 2. UI 流程控管
# =========================
st.set_page_config(page_title="專業進銷存管理系統", layout="wide")
init_db()
df_s, df_i = load_data()

if "step" not in st.session_state: st.session_state.step = "select_store"
if "record_date" not in st.session_state: st.session_state.record_date = date.today()

# --- 步驟 1：分店選擇 ---
if st.session_state.step == "select_store":
    st.title("🏠 選擇分店")
    if df_s is not None:
        for s in df_s['分店名稱'].unique():
            if st.button(f"📍 {s}", use_container_width=True):
                st.session_state.store = s
                st.session_state.step = "select_vendor"
                st.rerun()

# --- 步驟 2：廠商與日期選擇 ---
elif st.session_state.step == "select_vendor":
    st.title(f"🏢 {st.session_state.store}")
    st.session_state.record_date = st.date_input("🗓️ 紀錄/送貨日期", value=st.session_state.record_date)
    
    col_v, col_r = st.columns([2, 1])
    with col_v:
        st.subheader("廠商列表")
        vendors = sorted(df_i['廠商名稱'].unique())
        for v in vendors:
            if st.button(f"📦 {v}", use_container_width=True):
                st.session_state.vendor = v
                st.session_state.step = "fill_items"
                st.rerun()
    
    with col_r:
        st.subheader("功能選單")
        if st.button("📄 產生今日叫貨報表", type="primary", use_container_width=True):
            st.session_state.step = "export"
            st.rerun()
        if st.button("📊 期間分析查詢", use_container_width=True):
            st.session_state.step = "analysis"
            st.rerun()
        if st.button("⬅️ 返回分店列表", use_container_width=True):
            st.session_state.step = "select_store"
            st.rerun()

# --- 步驟 3：填寫明細 ---
elif st.session_state.step == "fill_items":
    col_title, col_back = st.columns([4, 1])
    with col_title:
        st.title(f"📝 {st.session_state.vendor}")
        st.caption(f"分店：{st.session_state.store} | 日期：{st.session_state.record_date}")
    with col_back:
        if st.button("❌ 不儲存，返回", use_container_width=True):
            st.session_state.step = "select_vendor"
            st.rerun()

    items = df_i[df_i['廠商名稱'] == st.session_state.vendor]
    date_str = st.session_state.record_date.isoformat()
    
    with st.form("inventory_form"):
        temp_data = []
        for _, row in items.iterrows():
            name, unit = row['品項名稱'], row['單位']
            prev_s, prev_p = get_previous_data(st.session_state.store, name, date_str)
            
            st.write(f"---")
            st.markdown(f"**{name}** ({unit})")
            
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                st.info(f"上次結餘：{prev_s + prev_p}")
                t_s = st.number_input(f"這次剩餘", min_value=0, step=1, key=f"s_{name}")
            with c2:
                t_p = st.number_input(f"這次叫貨", min_value=0, step=1, key=f"p_{name}")
            with c3:
                usage = prev_s + prev_p - t_s
                st.success(f"計算使用量：{usage}")
            
            temp_data.append((st.session_state.store, st.session_state.vendor, name, prev_s, prev_p, int(t_s), int(t_p), int(usage), date_str))
            
        if st.form_submit_button("💾 儲存並返回廠商列表", use_container_width=True):
            conn = get_conn()
            for r in temp_data:
                conn.execute("""
                    INSERT INTO records (store_name, vendor_name, item_name, last_stock, last_purchase, this_stock, this_purchase, usage_qty, record_date) 
                    VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(record_date, store_name, item_name) DO UPDATE SET
                    this_stock=excluded.this_stock, this_purchase=excluded.this_purchase, usage_qty=excluded.usage_qty
                """, r)
            conn.commit(); conn.close()
            st.session_state.step = "select_vendor"
            st.rerun()

# --- 步驟 4：產生報表 (標題優化重點) ---
elif st.session_state.step == "export":
    date_str = st.session_state.record_date.isoformat()
    st.title(f"📋 {date_str} 叫貨報表")
    conn = get_conn()
    
    # 只抓有叫貨的
    recs = conn.execute("""
        SELECT vendor_name, item_name, last_stock, last_purchase, this_stock, usage_qty, this_purchase
        FROM records 
        WHERE store_name=? AND record_date=? AND this_purchase > 0
        ORDER BY vendor_name, item_name
    """, (st.session_state.store, date_str)).fetchall()
    conn.close()
    
    if not recs:
        st.warning(f"{date_str} 目前沒有任何叫貨紀錄。")
    else:
        # 標題優化處理
        df_display = pd.DataFrame(recs, columns=['廠商', '品項名稱', '上次庫存', '上次叫貨', '這次剩餘', '期間使用量', '本次叫貨量'])
        
        st.subheader("🔍 今日叫貨數據對照表")
        st.table(df_display) # 使用 table 或 dataframe
        
        # LINE 格式
        output = f"【{st.session_state.store}】叫貨單 ({date_str})\n"
        output += "--------------------\n"
        current_v = ""
        for r in recs:
            if r['vendor_name'] != current_v:
                current_v = r['vendor_name']
                output += f"\n廠商：{current_v}\n"
            output += f"● {r['item_name']}：{int(r['this_purchase'])}\n"
        
        st.subheader("📱 LINE 複製格式")
        st.text_area("全選複製：", value=output, height=300)
    
    if st.button("⬅️ 返回廠商列表"): st.session_state.step = "select_vendor"; st.rerun()

# --- 步驟 5：分析 ---
elif st.session_state.step == "analysis":
    st.title("📊 期間使用量彙整")
    c1, c2 = st.columns(2)
    start = c1.date_input("起始日", value=date.today() - timedelta(days=7))
    end = c2.date_input("結束日", value=date.today())
    
    conn = get_conn()
    query = """
        SELECT vendor_name, item_name, SUM(usage_qty) as total_usage 
        FROM records 
        WHERE store_name = ? AND record_date BETWEEN ? AND ?
        GROUP BY vendor_name, item_name 
        HAVING total_usage <> 0
        ORDER BY vendor_name, total_usage DESC
    """
    analysis = conn.execute(query, (st.session_state.store, start.isoformat(), end.isoformat())).fetchall()
    conn.close()
    
    if analysis:
        df_ana = pd.DataFrame(analysis, columns=['廠商名稱', '品項名稱', '總消耗數量'])
        st.table(df_ana)
    else:
        st.info("該期間尚無數據。")
    
    if st.button("⬅️ 返回廠商列表"): st.session_state.step = "select_vendor"; st.rerun()
