"""
分店管理頁（暫時版本）
"""

import streamlit as st
import pandas as pd

from oms_core import read_table


def page_store_admin():

    st.title("🏬 分店管理")

    stores_df = read_table("stores")

    if stores_df.empty:
        st.info("目前沒有分店資料")
        return

    show_df = stores_df.copy()

    st.dataframe(
        show_df,
        use_container_width=True,
        hide_index=True,
    )
