import streamlit as st

from core.data_sources import load_store_df, guess_store_name_col


st.title("🏠 Home｜選擇分店")

# 初始化 session_state
if "store_selected" not in st.session_state:
    st.session_state.store_selected = None

# 讀取分店主檔
try:
    store_df = load_store_df()
except Exception as e:
    st.error(f"❌ 分店主檔讀取失敗：{e}")
    st.stop()

if store_df is None or len(store_df) == 0:
    st.warning("⚠️ 分店主檔是空的，請確認 data/品項總覽.xlsx - 分店.csv")
    st.stop()

name_col = guess_store_name_col(store_df)
if not name_col:
    st.error("❌ 無法判斷分店名稱欄位（分店主檔沒有欄位）")
    st.stop()

stores = (
    store_df[name_col]
    .dropna()
    .astype(str)
    .str.strip()
    .replace("", None)
    .dropna()
    .unique()
    .tolist()
)

if not stores:
    st.warning("⚠️ 分店名稱欄位沒有可用資料，請檢查分店 CSV")
    st.stop()

st.caption("提示：這個頁面先確保 2.0 架構能穩定讀取 data/，後續再把 1.0 的 UI/流程搬進來。")

picked = st.selectbox("選擇分店", options=stores, index=0)

col1, col2 = st.columns([1, 2])
with col1:
    if st.button("✅ 確認選擇", use_container_width=True):
        st.session_state.store_selected = picked
        st.success(f"已選擇：{picked}")

with col2:
    st.write("目前選擇：", st.session_state.store_selected or "（尚未選擇）")
