import streamlit as st

def apply_global_style():
    st.set_page_config(page_title="OMS 系統", layout="centered")
    st.markdown(
        """
        <style>
        [data-testid="stTable"] td:nth-child(1),
        [data-testid="stTable"] th:nth-child(1),
        [data-testid="stDataFrame"] [role="row"] [role="gridcell"]:first-child {
            display: none !important;
        }
        [data-testid="stTable"] td,
        [data-testid="stTable"] th,
        [data-testid="stDataFrame"] [role="gridcell"],
        [data-testid="stDataFrame"] [role="columnheader"] {
            font-size: 11px !important;
            font-weight: 400 !important;
            padding: 4px 2px !important;
            line-height: 1.1 !important;
        }
        [data-testid="stTable"] th,
        [data-testid="stDataFrame"] [role="columnheader"] { font-weight: 600 !important; }

        div[data-testid="stNumberInputStepUp"],
        div[data-testid="stNumberInputStepDown"] { display: none !important; }
        input[type=number] { -moz-appearance: textfield !important; -webkit-appearance: none !important; margin: 0 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
