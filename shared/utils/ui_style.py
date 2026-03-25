from __future__ import annotations

import pandas as pd
import streamlit as st

PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "scrollZoom": False,
    "doubleClick": False,
    "editable": False,
    "modeBarButtonsToRemove": [
        "zoom2d",
        "pan2d",
        "select2d",
        "lasso2d",
        "zoomIn2d",
        "zoomOut2d",
        "autoScale2d",
        "resetScale2d",
        "hoverClosestCartesian",
        "hoverCompareCartesian",
        "toggleSpikelines",
    ],
}

def apply_global_style():
    st.markdown(
        """
        <style>

        /* 移除表格最左側序號 */
        [data-testid="stTable"] td:nth-child(1),
        [data-testid="stTable"] th:nth-child(1),
        [data-testid="stDataFrame"] [role="row"] [role="gridcell"]:first-child {
            display: none !important;
        }

        /* 表格微縮 */
        [data-testid="stTable"] td,
        [data-testid="stTable"] th,
        [data-testid="stDataFrame"] [role="gridcell"],
        [data-testid="stDataFrame"] [role="columnheader"] {
            font-size: 11px !important;
            padding: 4px 2px !important;
        }

        /* 隱藏 number_input +/- */
        div[data-testid="stNumberInputStepUp"],
        div[data-testid="stNumberInputStepDown"] {
            display: none !important;
        }

        input[type=number] {
            -moz-appearance: textfield !important;
            -webkit-appearance: none !important;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )

def apply_table_report_style():
    st.markdown(
        """
        <style>
        [data-testid="stDataFrameToolbar"] {
            display: none !important;
        }

        [data-testid="stDataFrame"] [role="columnheader"] {
            pointer-events: none !important;
        }

        [data-testid="stDataFrame"] [role="gridcell"] {
            pointer-events: none !important;
        }

        [data-testid="stDataFrame"] div[role="grid"] {
            pointer-events: auto !important;
        }

        [data-testid="stDataFrame"] [role="columnheader"],
        [data-testid="stDataFrame"] [role="gridcell"] {
            font-size: 11px !important;
            line-height: 1.1 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_report_dataframe(
    df: pd.DataFrame,
    column_config: dict | None = None,
    height: int | None = None,
):
    apply_table_report_style()

    dataframe_kwargs = {
        "use_container_width": True,
        "hide_index": True,
        "column_config": column_config or {},
    }

    # 某些 Streamlit 版本不接受 height=None
    if height is not None:
        dataframe_kwargs["height"] = height

    st.dataframe(
        df,
        **dataframe_kwargs,
    )

def export_csv_button(df, filename: str, label: str = "📥 匯出 CSV"):
    import streamlit as st

    if df is None or df.empty:
        st.caption("沒有資料可匯出")
        return

    csv_data = df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        label,
        csv_data,
        file_name=filename,
        mime="text/csv",
        use_container_width=False,
    )

