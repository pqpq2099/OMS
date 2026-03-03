import streamlit as st
from datetime import date

def init_session():
    if "store" not in st.session_state:
        st.session_state.store = ""
    if "vendor" not in st.session_state:
        st.session_state.vendor = ""
    if "record_date" not in st.session_state:
        st.session_state.record_date = date.today()
