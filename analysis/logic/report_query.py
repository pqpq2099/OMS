from __future__ import annotations

import pandas as pd
import streamlit as st

from shared.services.service_reports import get_report_shared_table_versions, read_report_table


REPORT_SHARED_TABLES = ("items", "vendors", "stores", "prices", "unit_conversions")


def load_report_shared_tables() -> dict[str, pd.DataFrame]:
    versions = get_report_shared_table_versions(REPORT_SHARED_TABLES)
    cache = st.session_state.get("_reports_shared_tables_cache")
    if isinstance(cache, dict) and cache.get("versions") == versions:
        data = cache.get("data", {})
        if data:
            return {k: v.copy() for k, v in data.items()}

    data = {name: read_report_table(name) for name in REPORT_SHARED_TABLES}
    st.session_state["_reports_shared_tables_cache"] = {
        "versions": versions,
        "data": {k: v.copy() for k, v in data.items()},
    }
    return {k: v.copy() for k, v in data.items()}


def clear_report_shared_tables_cache():
    st.session_state.pop("_reports_shared_tables_cache", None)
