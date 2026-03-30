from __future__ import annotations

from datetime import date

import pandas as pd

from shared.services.service_order_core import safe_float


def validate_order_submission(
    *,
    submit_rows: list[dict],
    vendor_items: pd.DataFrame,
    conversions_df: pd.DataFrame,
    record_date: date,
    is_initial_stock: bool,
) -> list[str]:
    errors: list[str] = []

    has_any_order = any(safe_float(row["order_qty"]) > 0 for row in submit_rows)
    has_any_stock_gt_zero = any(safe_float(row["stock_qty"]) > 0 for row in submit_rows)

    if is_initial_stock and (not has_any_order) and (not has_any_stock_gt_zero):
        errors.append("首次盤點不可全部輸入 0，至少要有庫存或叫貨資料。")

    # 無價格品項不阻擋送出（全局規則）：price check 僅做參考，不 append error

    return errors
