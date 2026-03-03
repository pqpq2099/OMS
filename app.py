import streamlit as st
from core.ui_style import apply_global_style
from core.session import init_session

apply_global_style()
init_session()

st.title("OMS 2.0")
st.caption("請使用左側側欄進入：Home / Inventory / Export / Analysis / History")
