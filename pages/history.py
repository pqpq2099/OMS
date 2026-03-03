import streamlit as st
import pandas as pd
from datetime import date, timedelta

try:
    import plotly.express as px
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

from core.ui_style import apply_global_style
from core.session import init_session
from core.sheets_client import get_worksheet_data

apply_global_style()
init_session()

def plotly_report_config(filename: str = "oms_report") -> dict:
    return {
        "displayModeBar": True,
        "displaylogo": False,
        "scrollZoom": False,
        "doubleClick": False,
        "modeBarButtonsToRemove": [
            "zoom2d","pan2d","select2d","lasso2d",
            "zoomIn2d","zoomOut2d","autoScale2d","resetScale2d",
            "hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines",
        ],
        "toImageButtonOptions": {"format": "png","filename": filename,"scale": 2},
    }

st.title("📜 History | 分店歷史庫")

if not st.session_state.store:
    st.info("請先到 Home 選擇分店")
    st.stop()

v_df = get_worksheet_data(f"{st.session_state.store}_紀錄")
if v_df.empty:
    st.info("💡 尚無歷史紀錄可供查看。")
    st.stop()

c_h_date1, c_h_date2 = st.columns(2)
h_start = c_h_date1.date_input("起始日期", value=date.today() - timedelta(7))
h_end = c_h_date2.date_input("結束日期", value=date.today())

t1, t2 = st.tabs(["📋 明細", "📈 趨勢"])

with t1:
    v_df["日期_dt"] = pd.to_datetime(v_df["日期"], errors="coerce").dt.date
    temp_filt = v_df[(v_df["日期_dt"] >= h_start) & (v_df["日期_dt"] <= h_end)].copy()

    if temp_filt.empty:
        st.info("💡 此區間內無紀錄。")
    else:
        col_v, col_i = st.columns(2)
        all_v_m = ["全部廠商"] + sorted(temp_filt["廠商"].unique().tolist())
        sel_v_m = col_v.selectbox("📦 1. 選擇廠商", options=all_v_m, index=0)

        f_df = temp_filt.copy()
        if sel_v_m != "全部廠商":
            f_df = f_df[f_df["廠商"] == sel_v_m]

        all_i_m = ["全部品項"] + sorted(f_df["品項名稱"].unique().tolist())
        sel_i_m = col_i.selectbox("🏷️ 2. 選擇品項", options=all_i_m, index=0)

        if sel_i_m != "全部品項":
            f_df = f_df[f_df["品項名稱"] == sel_i_m]

        if "日期" in f_df.columns:
            f_df["顯示日期"] = pd.to_datetime(f_df["日期"], errors="coerce").dt.strftime("%m-%d")

        cols_order = ["顯示日期", "廠商", "品項名稱", "單位", "上次剩餘", "上次叫貨", "本次剩餘", "本次叫貨", "期間消耗"]
        final_cols = [c for c in cols_order if c in f_df.columns]
        st.dataframe(f_df[final_cols].sort_values("顯示日期", ascending=False), use_container_width=True, hide_index=True)

with t2:
    if not HAS_PLOTLY:
        st.info("💡 Plotly 未安裝，無法顯示趨勢圖。")
    else:
        col_v_h, col_i_h = st.columns(2)
        all_v_h = sorted(v_df["廠商"].dropna().unique().tolist())
        sel_v_h = col_v_h.selectbox("📦 1. 選擇廠商", options=all_v_h)

        v_filtered = v_df[v_df["廠商"] == sel_v_h]
        all_i_h = sorted(v_filtered["品項名稱"].dropna().unique().tolist())
        sel_i_h = col_i_h.selectbox("🏷️ 2. 選擇品項", options=all_i_h)

        p_df = v_filtered[v_filtered["品項名稱"] == sel_i_h].copy()
        p_df["日期標記"] = pd.to_datetime(p_df["日期"], errors="coerce").dt.strftime("%Y-%m-%d")
        p_df = p_df.sort_values("日期標記")

        if p_df.empty:
            st.info("💡 此品項在此區間無資料。")
        else:
            fig = px.line(p_df, x="日期標記", y="期間消耗", markers=True, title=f"📈 【{sel_i_h}】消耗趨勢")
            fig.update_layout(dragmode=False)
            st.plotly_chart(fig, use_container_width=True, config=plotly_report_config("history_usage"))
