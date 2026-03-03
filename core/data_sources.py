import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
CSV_ITEMS = DATA_DIR / "品項總覽.xlsx - 品項.csv"
CSV_STORE = DATA_DIR / "品項總覽.xlsx - 分店.csv"
CSV_PRICE = DATA_DIR / "品項總覽.xlsx - 價格歷史.csv"

def load_csv_safe(path: Path) -> pd.DataFrame | None:
    for enc in ["utf-8-sig", "utf-8", "cp950", "big5"]:
        try:
            df = pd.read_csv(path, encoding=enc)
            return df.map(lambda x: str(x).strip() if isinstance(x, str) else x)
        except Exception:
            continue
    return None

def load_master_data():
    df_s = load_csv_safe(CSV_STORE)
    df_i = load_csv_safe(CSV_ITEMS)
    df_pr = load_csv_safe(CSV_PRICE)

    item_display_map = {}
    if df_i is not None and not df_i.empty and {"品項ID","品項名稱"}.issubset(df_i.columns):
        item_display_map = (
            df_i.drop_duplicates("品項ID")
               .set_index("品項ID")["品項名稱"]
               .to_dict()
        )

    return df_s, df_i, df_pr, item_display_map
