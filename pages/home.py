import streamlit as st
from core.ui_style import apply_global_style
from core.session import init_session
from core.data_sources import load_master_data

apply_global_style()
init_session()

df_s, df_i, df_pr, item_map = load_master_data()

st.title("🏠 Home | 選擇分店")
st.caption("提示：這頁面先確保 2.0 架構能穩定讀取 data/，後續再把 1.0 的 UI/流程搬進來。")

if df_s is None or df_s.empty or "分店名稱" not in df_s.columns:
    st.warning("⚠️ 分店資料讀取失敗或缺少欄位：分店名稱")
    st.stop()

store = st.selectbox("選擇分店", options=sorted(df_s["分店名稱"].unique().tolist()))
if st.button("✅ 確認選擇", use_container_width=True):
    st.session_state.store = store
    st.success(f"已選擇：{store}")
