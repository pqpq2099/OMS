from __future__ import annotations

from datetime import date

import pandas as pd

from oms_core import _safe_float, get_base_unit_cost, read_table
from utils.utils_units import convert_to_base


def validate_order_submission(
    *,
    submit_rows: list[dict],
    vendor_items: pd.DataFrame,
    conversions_df: pd.DataFrame,
    record_date: date,
    is_initial_stock: bool,
) -> list[str]:
    errors: list[str] = []

    has_any_order = any(_safe_float(row["order_qty"]) > 0 for row in submit_rows)
    has_any_stock_gt_zero = any(_safe_float(row["stock_qty"]) > 0 for row in submit_rows)

    if is_initial_stock and (not has_any_order) and (not has_any_stock_gt_zero):
        errors.append("首次盤點不可全部輸入 0，至少要有庫存或叫貨資料。")

    prices_df_for_check = read_table("prices")
    for row in submit_rows:
        if _safe_float(row["order_qty"]) <= 0:
            continue

        try:
            order_base_qty, _ = convert_to_base(
                item_id=row["item_id"],
                qty=row["order_qty"],
                from_unit=row["order_unit"],
                items_df=vendor_items,
                conversions_df=conversions_df,
                as_of_date=record_date,
            )
            base_unit_cost = get_base_unit_cost(
                item_id=row["item_id"],
                target_date=record_date,
                items_df=vendor_items,
                prices_df=prices_df_for_check,
                conversions_df=conversions_df,
            )
            check_amount = round(
                float(order_base_qty) * float(base_unit_cost or 0),
                1,
            )
        except Exception:
            check_amount = 0

        if check_amount <= 0:
            errors.append(f"{row['item_name']} 缺少有效單價或換算結果。")

    return errors
