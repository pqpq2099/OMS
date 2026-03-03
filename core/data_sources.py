from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st

# ============================================================
# CSV paths
# ============================================================
CSV_ITEMS = Path("data/品項總覽.xlsx - 品項.csv")
CSV_STORE = Path("data/品項總覽.xlsx - 分店.csv")
CSV_PRICE = Path("data/品項總覽.xlsx - 價格歷史.csv")


def _assert_exists(p: Path) -> None:
    if not p.exists():
        raise FileNotFoundError(f"找不到檔案：{p.as_posix()}")


@st.cache_data(show_spinner=False)
def load_items_df() -> pd.DataFrame:
    _assert_exists(CSV_ITEMS)
    return pd.read_csv(CSV_ITEMS)


@st.cache_data(show_spinner=False)
def load_store_df() -> pd.DataFrame:
    _assert_exists(CSV_STORE)
    return pd.read_csv(CSV_STORE)


@st.cache_data(show_spinner=False)
def load_price_df() -> pd.DataFrame:
    _assert_exists(CSV_PRICE)
    return pd.read_csv(CSV_PRICE)


def guess_store_name_col(df: pd.DataFrame) -> str:
    """
    用「最不容易壞」的方式猜分店名稱欄位。
    找不到就用第一欄。
    """
    candidates = ["分店", "分店名稱", "門市", "門市名稱", "store", "store_name", "name"]
    cols = list(df.columns)
    for c in candidates:
        if c in cols:
            return c
    return cols[0] if cols else ""
