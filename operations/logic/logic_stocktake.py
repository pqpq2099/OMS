from __future__ import annotations

import pandas as pd

from operations.services.service_stocktake import get_stocktake_items, get_stocktake_units


def build_stocktake_submit_df(results: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(results)


def build_stocktake_page_tables(store_id: str = "") -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    載入盤點頁所需的品項與單位資料。
    store_id 預留供未來依門市篩選使用；目前品項為品牌層級，不做門市過濾。
    回傳 (items_df, units_df)；items_df 為空時觸發 page 的 empty guard。
    """
    items_df = get_stocktake_items()
    if items_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    units_df = get_stocktake_units(items_df)
    return items_df, units_df
