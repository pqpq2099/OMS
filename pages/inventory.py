import streamlit as st
import pandas as pd
from datetime import date
from core.ui_style import apply_global_style
from core.session import init_session
from core.data_sources import load_master_data
from core.sheets_client import get_cloud_data, sync_to_cloud
from core.price_engine import get_price_by_date

apply_global_style()
init_session()

df_s, df_i, df_pr, item_display_map = load_master_data()

st.title("🧾 Inventory | 盤點 / 叫貨")

if not st.session_state.store:
    st.info("請先到 Home 選擇分店")
    st.stop()

st.subheader(f"🏢 {st.session_state.store}")
st.session_state.record_date = st.date_input("🗓️ 盤點日期", value=st.session_state.record_date)

if df_i is None or df_i.empty or "廠商名稱" not in df_i.columns:
    st.warning("⚠️ 品項資料讀取失敗或缺少欄位：廠商名稱")
    st.stop()

vendors = sorted(df_i["廠商名稱"].unique().tolist())
vendor = st.selectbox("選擇廠商", options=vendors)

if st.button("➡️ 進入盤點", type="primary", use_container_width=True):
    st.session_state.vendor = vendor
    st.session_state.history_df = get_cloud_data()

st.write("---")

if not st.session_state.get("vendor"):
    st.info("先選廠商並進入盤點")
    st.stop()

st.title(f"📝 {st.session_state.vendor}")

items = df_i[df_i["廠商名稱"] == st.session_state.vendor]
hist_df = st.session_state.get("history_df", pd.DataFrame())

# 上次參考（同你 1.0）
ref_list = []
if not hist_df.empty:
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

with st.form("inventory_form"):
    temp_data = []
    last_item_display_name = ""

    h1, h2, h3 = st.columns([6, 1, 1])
    h1.write("<b>品項名稱</b>", unsafe_allow_html=True)
    h2.write("<div style='text-align:center;'><b>庫</b></div>", unsafe_allow_html=True)
    h3.write("<div style='text-align:center;'><b>進</b></div>", unsafe_allow_html=True)

    for _, row in items.iterrows():
        f_id = str(row["品項ID"]).strip()
        d_n = str(row["品項名稱"]).strip()
        unit = str(row["單位"]).strip()

        default_price = pd.to_numeric(row.get("單價", 0), errors="coerce")
        price = get_price_by_date(f_id, st.session_state.record_date, df_pr) or float(default_price)

        p_s, p_p, avg_usage, suggest_qty = 0.0, 0.0, 0.0, 0.0
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
            st.caption(f"{unit} (前結:{p_s:.1f} | 單價:{price:.1f} | 💡建議:{suggest_qty:.1f})")
            last_item_display_name = d_n

        with c2:
            t_s = st.number_input("庫", min_value=0.0, step=0.1, key=f"s_{f_id}", format="%g", value=None, label_visibility="collapsed")
        with c3:
            t_p = st.number_input("進", min_value=0.0, step=0.1, key=f"p_{f_id}", format="%g", value=None, label_visibility="collapsed")

        t_s_v = t_s if t_s is not None else 0.0
        t_p_v = t_p if t_p is not None else 0.0
        usage = p_s - t_s_v

        temp_data.append([
            str(st.session_state.record_date),
            st.session_state.store,
            st.session_state.vendor,
            f_id,
            d_n,
            unit,
            p_s,
            p_p,
            t_s_v,
            t_p_v,
            usage,
            float(price),
            float(round(t_p_v * price, 1)),
        ])

    if st.form_submit_button("💾 儲存並同步數據", use_container_width=True):
        valid = [d for d in temp_data if d[8] >= 0 or d[9] > 0]
        if valid and sync_to_cloud(pd.DataFrame(valid)):
            st.success("✅ 儲存成功")
            st.session_state.vendor = ""
            st.rerun()
