from __future__ import annotations

import pandas as pd


def build_stocktake_submit_df(results: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(results)


def build_stocktake_page_tables():
    return pd.DataFrame(), pd.DataFrame()
