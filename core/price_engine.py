import pandas as pd
from datetime import date

def get_price_by_date(item_id: str, target_date: date, price_df: pd.DataFrame | None) -> float:
    if price_df is None or price_df.empty:
        return 0.0

    df = price_df.copy()
    required = {"品項ID", "單價", "生效日"}
    if not required.issubset(set(df.columns)):
        return 0.0

    if "結束日" not in df.columns:
        df["結束日"] = pd.NaT

    df["品項ID"] = df["品項ID"].astype(str).str.strip()
    df["單價"] = pd.to_numeric(df["單價"], errors="coerce").fillna(0)
    df["生效日"] = pd.to_datetime(df["生效日"], errors="coerce")
    df["結束日"] = pd.to_datetime(df["結束日"], errors="coerce")

    target_ts = pd.Timestamp(target_date)
    matched = df[
        (df["品項ID"] == str(item_id).strip())
        & (df["生效日"].notna())
        & (df["生效日"] <= target_ts)
        & (df["結束日"].isna() | (df["結束日"] >= target_ts))
    ].sort_values("生效日")

    return float(matched.iloc[-1]["單價"]) if not matched.empty else 0.0
