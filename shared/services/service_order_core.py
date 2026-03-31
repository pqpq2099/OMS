from __future__ import annotations

from datetime import date

import pandas as pd

from shared.utils.common_helpers import (
    _clean_option_list,
    _get_active_df,
    _item_display_name,
    _label_store,
    _label_vendor,
    _norm,
    _now_ts,
    _parse_date,
    _safe_float,
    _sort_items_for_operation,
    _status_hint,
)
from shared.services.report_calculations import (
    _build_latest_item_metrics_df,
    _get_latest_price_for_item,
    _get_latest_stock_qty_in_display_unit,
    get_base_unit_cost,
)
from shared.services.spreadsheet_backend import get_table_versions, read_table


def build_latest_item_metrics_df(*, store_id: str, as_of_date: date) -> pd.DataFrame:
    return _build_latest_item_metrics_df(store_id=store_id, as_of_date=as_of_date)


def clean_option_list(values) -> list[str]:
    return _clean_option_list(values)


def get_active_df(df: pd.DataFrame) -> pd.DataFrame:
    return _get_active_df(df)


def get_latest_price_for_item(prices_df: pd.DataFrame, item_id: str, target_date: date) -> float:
    return _get_latest_price_for_item(prices_df, item_id, target_date)


def get_latest_stock_qty_in_display_unit(*, stocktakes_df: pd.DataFrame, stocktake_lines_df: pd.DataFrame, items_df: pd.DataFrame, conversions_df: pd.DataFrame, store_id: str, item_id: str, display_unit: str, as_of_date: date) -> float:
    return _get_latest_stock_qty_in_display_unit(
        stocktakes_df=stocktakes_df,
        stocktake_lines_df=stocktake_lines_df,
        items_df=items_df,
        conversions_df=conversions_df,
        store_id=store_id,
        item_id=item_id,
        display_unit=display_unit,
        as_of_date=as_of_date,
    )


def item_display_name(row) -> str:
    return _item_display_name(row)


def label_store(row) -> str:
    return _label_store(row)


def label_vendor(row) -> str:
    return _label_vendor(row)


def norm(value) -> str:
    return _norm(value)


def now_ts() -> str:
    return _now_ts()


def parse_date(value):
    return _parse_date(value)


def safe_float(value, default: float = 0.0) -> float:
    return _safe_float(value, default)


def status_hint(total_stock_ref: float, daily_avg: float, suggest_qty: float):
    return _status_hint(total_stock_ref, daily_avg, suggest_qty)


def read_order_table(name: str) -> pd.DataFrame:
    return read_table(name)


def get_order_table_versions(table_names) -> dict:
    return get_table_versions(table_names)


__all__ = [
    'build_latest_item_metrics_df',
    'clean_option_list',
    'get_active_df',
    'get_base_unit_cost',
    'get_latest_price_for_item',
    'get_latest_stock_qty_in_display_unit',
    'get_order_table_versions',
    'item_display_name',
    'label_store',
    'label_vendor',
    'norm',
    'now_ts',
    'parse_date',
    'read_order_table',
    'safe_float',
    'status_hint',
    'sort_items_for_operation',
]


def sort_items_for_operation(df: pd.DataFrame) -> pd.DataFrame:
    return _sort_items_for_operation(df)
