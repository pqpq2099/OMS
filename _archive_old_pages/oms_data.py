# ============================================================
# ORIVIA OMS - Data Access
# 最小骨架版：先放資料層入口
# ============================================================

from __future__ import annotations

import pandas as pd


def read_table(table_name: str) -> pd.DataFrame:
    """
    骨架版占位函式。
    之後在這裡接 Google Sheets：
    - brands
    - stores
    - vendors
    - items
    - prices
    - stocktakes
    - purchase_orders
    等等
    """
    return pd.DataFrame()


def write_table(table_name: str, df: pd.DataFrame) -> None:
    """
    骨架版占位函式。
    之後在這裡實作整表寫回。
    """
    _ = table_name
    _ = df


def append_rows(table_name: str, df: pd.DataFrame) -> None:
    """
    骨架版占位函式。
    之後在這裡實作追加資料列。
    """
    _ = table_name
    _ = df
