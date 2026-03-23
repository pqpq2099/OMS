from __future__ import annotations

from oms_core import _norm, _safe_float, read_table


def get_existing_stock_map(stocktake_id: str) -> dict[str, float]:
    if not stocktake_id:
        return {}

    stock_lines_df = read_table("stocktake_lines")
    if stock_lines_df.empty or "stocktake_id" not in stock_lines_df.columns:
        return {}

    work = stock_lines_df[
        stock_lines_df["stocktake_id"].astype(str).str.strip() == str(stocktake_id).strip()
    ].copy()

    result = {}
    for _, row in work.iterrows():
        item_id = _norm(row.get("item_id", ""))
        if item_id:
            result[item_id] = _safe_float(row.get("stock_qty", row.get("qty", 0)))
    return result
