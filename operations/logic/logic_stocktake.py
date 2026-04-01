from __future__ import annotations

# [STUB] 此模組為盤點功能的佔位實作，尚未接回正式資料源。
# build_stocktake_page_tables() 永遠回傳空 DataFrame，page_stocktake 已加入
# empty guard，會顯示「尚未開放」提示而非空白畫面。
# 正式接回時：將 build_stocktake_page_tables() 改為讀取 DB，移除此 STUB 標記。

import pandas as pd


def build_stocktake_submit_df(results: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(results)


def build_stocktake_page_tables():
    # [STUB] 尚未實作正式資料載入，回傳空 DataFrame 以觸發 page 的受控提示
    return pd.DataFrame(), pd.DataFrame()
