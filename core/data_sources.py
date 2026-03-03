from pathlib import Path
import pandas as pd

# ============================================================
# Data file paths (CSV master)
# ============================================================
CSV_ITEMS = Path("data/品項總覽.xlsx - 品項.csv")
CSV_STORE = Path("data/品項總覽.xlsx - 分店.csv")
CSV_PRICE = Path("data/品項總覽.xlsx - 價格歷史.csv")


def load_items_df() -> pd.DataFrame:
    return pd.read_csv(CSV_ITEMS)


def load_store_df() -> pd.DataFrame:
    return pd.read_csv(CSV_STORE)


def load_price_df() -> pd.DataFrame:
    return pd.read_csv(CSV_PRICE)
  add data_sources module
