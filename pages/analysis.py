import streamlit as st
import pandas as pd
from datetime import date, timedelta

# Plotly (optional)
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
            "sendDataToCloud",
            "zoom3d","pan3d","orbitRotation","tableRotation",
            "resetCameraDefault3d","resetCameraLastSave3d","hoverClosest3d",
            "resetViews","toggleHover","resetViewMapbox",
        ],
        "toImageButtonOptions": {"format": "png","filename": filename,"scale": 2},
    }

st.title("📊 Analysis | 進銷存分析")

if not st.session_state.store:
    st.info("請先到 Home 選擇分店")
    st.stop()

a_df = get_worksheet_data("Records")
c_date1, c_date2 = st.columns(2)
start = c_date1.date_input("起始日期", value=date.today() - timedelta(14))
end = c_date2.date_input("結束日期", value=date.today())

if a_df.empty:
    st.error("❌ 無資料")
    st.stop()

a_df["日期"] = pd.to_datetime(a_df["日期"], errors="coerce").dt.date
current_store = str(st.session_state.store).strip()

filt = a_df[
    (a_df["店名"].astype(str).str.strip() == current_store)
    & (a_df["日期"] >= start)
    & (a_df["日期"] <= end)
].copy()

if filt.empty:
    st.warning(f"⚠️ 在 {start} 到 {end} 之間查無紀錄。")
    st.stop()

st.markdown("---")
col_v, col_i = st.columns(2)

all_v = ["全部廠商"] + sorted(filt["廠商"].dropna().unique().tolist())
selected_v = col_v.selectbox("📦 1. 選擇廠商", options=all_v, index=0)

v_filt = filt.copy()
if selected_v != "全部廠商":
    v_filt = v_filt[v_filt["廠商"] == selected_v]

all_i = ["全部品項"] + sorted(v_filt["品項名稱"].dropna().unique().tolist())
selected_item = col_i.selectbox("🏷️ 2. 選擇品項", options=all_i, index=0)

final_filt = v_filt.copy()
if selected_item != "全部品項":
    final_filt = final_filt[final_filt["品項名稱"] == selected_item]

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

t_detail, t_trend = st.tabs(["📋 明細", "📈 趨勢"])

with t_detail:
    required_cols = {"廠商", "品項名稱", "單位", "單價", "期間消耗", "本次叫貨", "總金額"}
    if not required_cols.issubset(set(final_filt.columns)):
        st.warning("⚠️ 欄位不足")
    else:
        summ_df = (
            final_filt.groupby(["廠商", "品項名稱", "單位", "單價"])
            .agg({"期間消耗": "sum", "本次叫貨": "sum", "總金額": "sum"})
            .reset_index()
        )
        st.dataframe(summ_df.sort_values("總金額", ascending=False), use_container_width=True, hide_index=True)

with t_trend:
    if not HAS_PLOTLY:
        st.info("💡 Plotly 未安裝，無法顯示圖表。")
    else:
        cfg = plotly_report_config("analysis")

        if {"日期", "總金額"}.issubset(final_filt.columns):
            trend_df = final_filt.copy()
            trend_df["日期_dt"] = pd.to_datetime(trend_df["日期"], errors="coerce")
            trend_daily = (
                trend_df.dropna(subset=["日期_dt"])
                .groupby("日期_dt", as_index=False)["總金額"]
                .sum()
                .sort_values("日期_dt")
            )
            if not trend_daily.empty:
                fig1 = px.line(trend_daily, x="日期_dt", y="總金額", markers=True, title="📈 採購金額趨勢")
                fig1.update_layout(dragmode=False)
                st.plotly_chart(fig1, use_container_width=True, config=cfg)

        if {"品項名稱", "總金額"}.issubset(final_filt.columns):
            rank_df = (
                final_filt.groupby("品項名稱", as_index=False)["總金額"]
                .sum()
                .sort_values("總金額", ascending=False)
                .head(20)
            )
            if not rank_df.empty:
                fig2 = px.bar(rank_df, x="品項名稱", y="總金額", title="📊 品項採購金額排行 (Top 20)")
                fig2.update_layout(dragmode=False)
                st.plotly_chart(fig2, use_container_width=True, config=cfg)
