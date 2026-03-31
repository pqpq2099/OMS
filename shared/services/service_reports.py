from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from shared.utils.common_helpers import (
    _clean_option_list,
    _get_active_df,
    _item_display_name,
    _norm,
    _parse_date,
    _safe_float,
)
from shared.services.report_calculations import (
    _build_inventory_history_summary_df,
    _build_latest_item_metrics_df,
    _build_purchase_detail_df,
    get_base_unit_cost,
)
from shared.utils.ui_style import render_report_dataframe as _render_report_dataframe
from shared.services.spreadsheet_backend import get_table_versions, read_table

REPORT_SHARED_TABLES = (
    "items",
    "vendors",
    "stores",
    "prices",
    "units",            
    "unit_conversions",
)


def render_report_dataframe(*args, **kwargs):
    return _render_report_dataframe(*args, **kwargs)


def get_report_shared_table_versions(table_names=REPORT_SHARED_TABLES):
    return get_table_versions(table_names)


def read_report_table(name: str) -> pd.DataFrame:
    return read_table(name)


def build_inventory_history_summary_df(*, store_id: str, start_date: date, end_date: date) -> pd.DataFrame:
    return _build_inventory_history_summary_df(store_id=store_id, start_date=start_date, end_date=end_date)


def build_latest_item_metrics_df(*, store_id: str, as_of_date: date) -> pd.DataFrame:
    return _build_latest_item_metrics_df(store_id=store_id, as_of_date=as_of_date)


def build_purchase_detail_df() -> pd.DataFrame:
    return _build_purchase_detail_df()


def clean_option_list(values) -> list[str]:
    return _clean_option_list(values)


def get_active_df(df: pd.DataFrame) -> pd.DataFrame:
    return _get_active_df(df)


def item_display_name(row) -> str:
    return _item_display_name(row)


def norm(value) -> str:
    return _norm(value)


def parse_date(value):
    return _parse_date(value)


def safe_float(value, default: float = 0.0) -> float:
    return _safe_float(value, default)


__all__ = [
    "REPORT_SHARED_TABLES",
    "build_inventory_history_summary_df",
    "build_latest_item_metrics_df",
    "build_purchase_detail_df",
    "clean_option_list",
    "get_active_df",
    "get_base_unit_cost",
    "get_report_shared_table_versions",
    "item_display_name",
    "norm",
    "parse_date",
    "read_report_table",
    "render_report_dataframe",
    "safe_float",
    "st",
]
