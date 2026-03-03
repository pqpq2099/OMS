import streamlit as st

st.set_page_config(page_title="OMS", layout="wide")

# 這裡不要放任何業務邏輯
# 2.0 原則：app.py 只當入口與導航提示

st.title("OMS 2.0（develop）")

st.info(
    "✅ 系統已啟動。請從左側選單進入 Home。\n\n"
    "接下來你會把 1.0 的功能逐步搬到 pages/ 與 core/。"
)
