from __future__ import annotations

import pandas as pd

from operations.services.service_stocktake import get_stocktake_items, get_stocktake_units
from operations.services.service_stocktake_write import (
    StocktakeWriteError,
    submit_stocktake,
)


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


def validate_stocktake_results(results: list[dict]) -> list[str]:
    """
    送出前驗證盤點結果。回傳錯誤訊息清單；空清單代表 PASS。

    規則：
    1. stock_qty 不可為負數
    2. order_qty 不可為負數
    3. stock_unit 不可空白
    4. order_qty > 0 時 order_unit 不可空白
    5. results 不可全為 0（至少一筆有庫存或叫貨量）
    """
    errors: list[str] = []

    # Rule 5: 全為 0 提前回傳
    has_any_value = any(
        float(r.get("stock_qty", 0) or 0) > 0
        or float(r.get("order_qty", 0) or 0) > 0
        for r in results
    )
    if not has_any_value:
        errors.append("請至少填寫一項庫存或叫貨數量再送出")
        return errors

    for r in results:
        item_id = str(r.get("item_id", "")).strip()
        stock_qty = float(r.get("stock_qty", 0) or 0)
        order_qty = float(r.get("order_qty", 0) or 0)
        stock_unit = str(r.get("stock_unit", "") or "").strip()
        order_unit = str(r.get("order_unit", "") or "").strip()

        if stock_qty < 0:
            errors.append(f"品項 {item_id}：庫存數量不可為負數")
        if order_qty < 0:
            errors.append(f"品項 {item_id}：叫貨數量不可為負數")
        if not stock_unit:
            errors.append(f"品項 {item_id}：請選擇庫存單位")
        if order_qty > 0 and not order_unit:
            errors.append(f"品項 {item_id}：叫貨數量 > 0 時請選擇叫貨單位")

    return errors


def submit_stocktake_results(
    results: list[dict],
    items_df: pd.DataFrame,
    store_id: str,
    actor: str,
) -> dict:
    """
    呼叫寫入服務層，回傳結果 dict：
      {"ok": True,  "stocktake_ids": [...], "error": ""}
      {"ok": False, "stocktake_ids": [],    "error": "...訊息..."}
    """
    try:
        stocktake_ids = submit_stocktake(results, items_df, store_id, actor)
        return {"ok": True, "stocktake_ids": stocktake_ids, "error": ""}
    except StocktakeWriteError as e:
        return {"ok": False, "stocktake_ids": [], "error": str(e)}
    except Exception as e:
        return {"ok": False, "stocktake_ids": [], "error": f"寫入失敗：{e}"}
