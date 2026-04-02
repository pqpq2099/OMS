# ============================================================
# ORIVIA OMS
# 檔案：operations/services/service_stocktake_write.py
# 說明：盤點寫入服務層
# 功能：將使用者盤點結果寫入 stocktakes、stocktake_lines 與 purchase_orders。
# 注意：本檔只負責寫入邏輯，不含任何 UI 邏輯。
# ============================================================

from __future__ import annotations

from datetime import date

import pandas as pd

from shared.services.data_backend import append_rows_by_header, read_table
from shared.services.report_calculations import get_base_unit_cost
from shared.services.service_id import (
    allocate_purchase_order_id,
    allocate_purchase_order_line_ids,
    allocate_stocktake_id,
    allocate_stocktake_line_ids,
)
from shared.services.table_contract import TABLE_CONTRACT
from shared.utils.common_helpers import _norm, _now_ts
from shared.utils.utils_units import convert_to_base


# ============================================================
# [W0] 例外類別
# ============================================================
class StocktakeWriteError(Exception):
    """盤點寫入可顯示錯誤。"""


# ============================================================
# [W1] 單位輔助函式
# ============================================================
def _build_display_to_unit_id_map() -> dict[str, str]:
    """
    建立 display_name → unit_id 的反查表。
    同時將 unit_id → unit_id 加入（pass-through），
    確保已是 unit_id 的值不受影響。
    """
    result: dict[str, str] = {}
    try:
        units_raw = read_table("units")
        if not units_raw.empty:
            for _, row in units_raw.iterrows():
                unit_id = _norm(row.get("unit_id", ""))
                display = (
                    _norm(row.get("unit_name_zh", ""))
                    or _norm(row.get("unit_name", ""))
                )
                if unit_id:
                    if display:
                        result[display] = unit_id  # display → unit_id
                    result[unit_id] = unit_id       # unit_id → unit_id (pass-through)
    except Exception:
        pass
    return result


def _resolve_unit_id(display_name: str, name_to_id: dict[str, str]) -> str:
    """
    將 display_name 轉成 unit_id。
    若 display_name 本身已是 unit_id（pass-through），直接回傳。
    若找不到對應，以 display_name 原值作為 fallback（適用單位名稱即 ID 的情境）。
    """
    text = _norm(display_name)
    return name_to_id.get(text, text)


def _safe_base_qty(
    *,
    item_id: str,
    qty: float,
    from_unit_display: str,
    items_df: pd.DataFrame,
    conversions_df: pd.DataFrame,
    name_to_id: dict[str, str],
    today: date,
) -> float:
    """
    將操作單位數量安全轉換成 base unit 數量。
    若找不到換算規則，以 1:1 為 fallback（qty 原值，不拋例外）。
    """
    from_unit = _resolve_unit_id(from_unit_display, name_to_id)
    try:
        base_qty, _ = convert_to_base(
            item_id=item_id,
            qty=qty,
            from_unit=from_unit,
            items_df=items_df,
            conversions_df=conversions_df,
            as_of_date=today,
        )
        return round(float(base_qty), 4)
    except Exception:
        # Fallback：找不到換算規則時以原數量作為 base_qty（1:1 假設）
        return round(float(qty), 4)


def _safe_unit_price(
    *,
    item_id: str,
    order_qty: float,
    order_base_qty: float,
    items_df: pd.DataFrame,
    prices_df: pd.DataFrame,
    conversions_df: pd.DataFrame,
    today: date,
) -> tuple[float, float]:
    """
    查詢 base_unit_cost 並計算 unit_price 與 amount。
    遵守 require_price=false 制度（CLAUDE.md § 6.4）：
    找不到有效價格時安全落地 unit_price=0, amount=0，不拋例外。
    回傳 (unit_price, amount)。
    """
    try:
        buc = get_base_unit_cost(
            item_id=item_id,
            target_date=today,
            items_df=items_df,
            prices_df=prices_df,
            conversions_df=conversions_df,
        )
        buc_f = float(buc) if buc is not None else 0.0
        if buc_f > 0:
            amount = round(order_base_qty * buc_f, 1)
            unit_price = round(amount / order_qty, 4) if order_qty > 0 else 0.0
            return unit_price, amount
    except Exception:
        pass
    return 0.0, 0.0


# ============================================================
# [W2] 表頭常數（對應 TABLE_CONTRACT）
# ============================================================
_STOCKTAKE_HEADER = list(TABLE_CONTRACT["stocktakes"]["columns_order"])
_STOCKTAKE_LINE_HEADER = list(TABLE_CONTRACT["stocktake_lines"]["columns_order"])
_PO_HEADER = list(TABLE_CONTRACT["purchase_orders"]["columns_order"])
_POL_HEADER = list(TABLE_CONTRACT["purchase_order_lines"]["columns_order"])


# ============================================================
# [W3] 主寫入函式
# ============================================================
def submit_stocktake(
    results: list[dict],
    items_df: pd.DataFrame,
    store_id: str,
    actor: str,
) -> dict:
    """
    將盤點結果寫入 stocktakes + stocktake_lines，
    並對 order_qty > 0 的品項建立 purchase_orders + purchase_order_lines。

    params:
        results   : render_item_row() 收集的 list[dict]
                    每筆含 {item_id, stock_qty, stock_unit, order_qty, order_unit}
        items_df  : get_stocktake_items() 回傳的品項 DataFrame
                    需含 item_id, name, default_vendor_id, base_unit 欄位
        store_id  : 門市 ID（來自 session_state）
        actor     : 操作者角色（來自 session_state.role）

    returns:
        {
          "stocktake_ids": list[str],  # 已建立的 stocktake_id 清單
          "po_ids":        list[str],  # 已建立的 po_id 清單（僅 order_qty > 0 時有值）
        }

    raises:
        StocktakeWriteError — 無有效品項可寫入時
    """
    today = date.today()
    now = _now_ts()

    # 載入換算與價格資料（各一次，供全部廠商群組共用）
    conversions_df = read_table("unit_conversions")
    prices_df = read_table("prices")
    name_to_id = _build_display_to_unit_id_map()

    # 建立 item_id → item 資訊快查表
    item_lookup: dict[str, dict] = {}
    for _, row in items_df.iterrows():
        item_id = _norm(row.get("item_id", ""))
        if item_id:
            item_lookup[item_id] = {
                "name": _norm(row.get("name", "") or item_id),
                "vendor_id": _norm(row.get("default_vendor_id", "")),
                "base_unit": _norm(row.get("base_unit", "")),
            }

    # 依廠商分組 results
    vendor_groups: dict[str, list[dict]] = {}
    for result in results:
        item_id = _norm(result.get("item_id", ""))
        if not item_id or item_id not in item_lookup:
            continue
        vendor_id = item_lookup[item_id]["vendor_id"]
        if not vendor_id:
            # 無廠商的品項跳過（需在品項主資料設定 default_vendor_id）
            continue
        vendor_groups.setdefault(vendor_id, []).append(result)

    if not vendor_groups:
        raise StocktakeWriteError(
            "無有效品項可寫入：請確認品項已設定廠商（default_vendor_id）"
        )

    created_stocktake_ids: list[str] = []
    created_po_ids: list[str] = []

    for vendor_id, vendor_results in vendor_groups.items():

        # ── Step 1: stocktakes 主記錄 ──────────────────────────────
        stocktake_id = allocate_stocktake_id()

        stocktake_row: dict = {
            "stocktake_id": stocktake_id,
            "store_id": store_id,
            "vendor_id": vendor_id,
            "stocktake_date": str(today),
            "stocktake_type": "regular",
            "status": "submitted",
            "created_by": actor,
            "created_at": now,
        }
        append_rows_by_header("stocktakes", _STOCKTAKE_HEADER, [stocktake_row])

        # ── Step 2: stocktake_lines 明細 ──────────────────────────
        line_ids = allocate_stocktake_line_ids(len(vendor_results))
        line_rows: list[dict] = []

        for i, result in enumerate(vendor_results):
            item_id = _norm(result.get("item_id", ""))
            meta = item_lookup.get(item_id, {})

            stock_qty = float(result.get("stock_qty", 0) or 0)
            order_qty = float(result.get("order_qty", 0) or 0)
            stock_unit_display = _norm(result.get("stock_unit", ""))
            order_unit_display = _norm(result.get("order_unit", ""))

            stock_unit_id = _resolve_unit_id(stock_unit_display, name_to_id)
            order_unit_id = _resolve_unit_id(order_unit_display, name_to_id)

            base_qty = _safe_base_qty(
                item_id=item_id,
                qty=stock_qty,
                from_unit_display=stock_unit_display,
                items_df=items_df,
                conversions_df=conversions_df,
                name_to_id=name_to_id,
                today=today,
            )

            line_rows.append({
                "stocktake_line_id": line_ids[i],
                "stocktake_id": stocktake_id,
                "store_id": store_id,
                "vendor_id": vendor_id,
                "item_id": item_id,
                "item_name": meta.get("name", item_id),
                "stock_qty": stock_qty,
                "stock_unit_id": stock_unit_id,
                "stock_unit": stock_unit_display,
                "base_qty": base_qty,
                "suggested_order_qty": 0,
                "order_qty": order_qty,
                "order_unit_id": order_unit_id,
                "created_at": now,
            })

        append_rows_by_header("stocktake_lines", _STOCKTAKE_LINE_HEADER, line_rows)
        created_stocktake_ids.append(stocktake_id)

        # ── Step 3: purchase_orders（僅 order_qty > 0 的品項）──────
        order_items = [
            r for r in vendor_results
            if float(r.get("order_qty", 0) or 0) > 0
        ]
        if not order_items:
            continue

        po_id = allocate_purchase_order_id()

        po_row: dict = {
            "po_id": po_id,
            "stocktake_id": stocktake_id,   # 關聯回來源盤點
            "store_id": store_id,
            "vendor_id": vendor_id,
            "po_date": str(today),
            "order_date": str(today),
            "status": "draft",
            "created_by": actor,
            "created_at": now,
        }
        append_rows_by_header("purchase_orders", _PO_HEADER, [po_row])

        # ── Step 4: purchase_order_lines ───────────────────────────
        pol_ids = allocate_purchase_order_line_ids(len(order_items))
        pol_rows: list[dict] = []

        for i, result in enumerate(order_items):
            item_id = _norm(result.get("item_id", ""))
            meta = item_lookup.get(item_id, {})

            order_qty = float(result.get("order_qty", 0) or 0)
            order_unit_display = _norm(result.get("order_unit", ""))
            order_unit_id = _resolve_unit_id(order_unit_display, name_to_id)

            order_base_qty = _safe_base_qty(
                item_id=item_id,
                qty=order_qty,
                from_unit_display=order_unit_display,
                items_df=items_df,
                conversions_df=conversions_df,
                name_to_id=name_to_id,
                today=today,
            )

            # 價格查詢（require_price=false：找不到價格安全落地 0，不阻擋送出）
            unit_price, amount = _safe_unit_price(
                item_id=item_id,
                order_qty=order_qty,
                order_base_qty=order_base_qty,
                items_df=items_df,
                prices_df=prices_df,
                conversions_df=conversions_df,
                today=today,
            )

            pol_rows.append({
                "po_line_id": pol_ids[i],
                "po_id": po_id,
                "store_id": store_id,
                "vendor_id": vendor_id,
                "item_id": item_id,
                "item_name": meta.get("name", item_id),
                "qty": order_qty,
                "order_qty": order_qty,
                "unit_id": order_unit_id,
                "order_unit": order_unit_display,
                "base_qty": order_base_qty,
                "unit_price": unit_price,
                "amount": amount,
                "created_at": now,
            })

        append_rows_by_header("purchase_order_lines", _POL_HEADER, pol_rows)
        created_po_ids.append(po_id)

    return {
        "stocktake_ids": created_stocktake_ids,
        "po_ids": created_po_ids,
    }
