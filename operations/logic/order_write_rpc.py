from __future__ import annotations

# =============================================================================
# [v1 STABLE — RPC PAYLOAD BUILDER]
# build_order_write_rpc_payload() 組裝 rpc_save_order_transaction 所需的完整
# payload，供 order_write._save_order_entry() 呼叫。
#
# 禁止事項：
#   - 不可回退為直接呼叫 write_stocktake_section / write_purchase_order_section
#   - payload 結構（key 名稱、型別）與 SQL function 嚴格對應，修改需同步更新
#     DB function 並重新執行 transaction validation
#   - _meta key 為 Python-only（傳回 po_id 給呼叫端），不傳入 SQL function
#   - 修改需重新跑 transaction validation 並輸出驗證報告
# =============================================================================

from datetime import date
import math

import pandas as pd
import streamlit as st

from shared.services.service_order_core import norm, safe_float, now_ts, get_base_unit_cost
from operations.logic.order_errors import UserDisplayError
from shared.services.service_id import (
    allocate_stocktake_id,
    allocate_purchase_order_id,
    allocate_many_ids,
)
from operations.logic.order_query_stock import get_existing_stock_line_id_map
from operations.logic.order_query_po import get_existing_po_line_id_map, get_existing_order_maps
from shared.utils.utils_units import convert_to_base
from shared.services.data_backend import read_table


def _sanitize_payload(obj, _path: str = "") -> object:
    """遞迴將 payload 內的 NaN / inf / -inf / pd.NA 轉為 0，並印出問題 key。"""
    if isinstance(obj, dict):
        return {k: _sanitize_payload(v, f"{_path}.{k}") for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_payload(item, f"{_path}[{i}]") for i, item in enumerate(obj)]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        pass  # NaN/inf replaced with 0
        return 0
    try:
        if pd.isna(obj):
            pass  # pd.NA replaced with 0
            return 0
    except (TypeError, ValueError):
        pass
    return obj


def build_order_write_rpc_payload(
    *,
    submit_rows,
    vendor_items,
    conversions_df,
    store_id: str,
    vendor_id: str,
    record_date: date,
    delivery_date: date,
    existing_stocktake_id: str = "",
    existing_po_id: str = "",
    is_initial_stock: bool = False,
) -> dict:
    """
    組裝 rpc_save_order_transaction 所需的 payload。
    複用 order_write_stock / order_write_po 的資料整理邏輯，不含任何商業規則 SQL。

    回傳 dict，包含以下 key：
      stocktake         - dict（必填）
      stocktake_lines   - list[dict]
      purchase_order    - dict | None（無叫貨時為 None）
      purchase_order_lines - list[dict]
      audit_logs        - list[dict]
      _meta             - {stocktake_id, po_id}（供呼叫端取 ID）
    """
    now = now_ts()
    user_id = norm(st.session_state.get("login_user", "")) or "SYSTEM"

    # ── Stocktake header ────────────────────────────────────────────
    stocktake_id = norm(existing_stocktake_id) or allocate_stocktake_id()
    is_new_stocktake = not norm(existing_stocktake_id)

    stocktake_payload: dict = {
        "stocktake_id": stocktake_id,
        "store_id": store_id,
        "vendor_id": vendor_id,
        "stocktake_date": str(record_date),
        "status": "done",
        "note": "initial_stock" if is_initial_stock else f"vendor={vendor_id}",
        "updated_at": now,
        "updated_by": user_id,
        "created_at": now,
        "created_by": user_id,
    }
    # ── Stocktake lines ─────────────────────────────────────────────
    existing_stl_id_map = get_existing_stock_line_id_map(existing_stocktake_id)

    stocktake_rows = [
        r for r in submit_rows if norm(r.get("item_id", ""))
    ]

    new_stl_item_ids = [
        norm(r.get("item_id", ""))
        for r in stocktake_rows
        if norm(r.get("item_id", "")) not in existing_stl_id_map
    ]
    new_stl_ids = allocate_many_ids("stocktake_lines", len(new_stl_item_ids))
    new_stl_id_map = dict(zip(new_stl_item_ids, new_stl_ids))

    stl_payload: list[dict] = []
    for r in stocktake_rows:
        item_id = norm(r.get("item_id", ""))
        if not item_id:
            continue
        try:
            base_qty, base_unit = convert_to_base(
                item_id=item_id,
                qty=safe_float(r.get("stock_qty", 0)),
                from_unit=norm(r.get("stock_unit", "")),
                items_df=vendor_items,
                conversions_df=conversions_df,
                as_of_date=record_date,
            )
        except Exception as e:
            raise UserDisplayError(
                f"{r.get('item_name', item_id)} stock conversion failed: {e}"
            )

        line_id = existing_stl_id_map.get(item_id) or new_stl_id_map.get(item_id, "")
        stl_payload.append({
            "stocktake_line_id": line_id,
            "stocktake_id": stocktake_id,
            "store_id": store_id,
            "vendor_id": vendor_id,
            "item_id": item_id,
            "item_name": r.get("item_name", ""),
            "qty": safe_float(r.get("stock_qty", 0)),
            "stock_qty": safe_float(r.get("stock_qty", 0)),
            "unit_id": norm(r.get("stock_unit", "")),
            "stock_unit": norm(r.get("stock_unit", "")),
            "stock_unit_id": norm(r.get("stock_unit", "")),
            "base_qty": round(base_qty, 3),
            "base_unit": base_unit,
            "created_at": now,
            "created_by": user_id,
            "updated_at": now,
            "updated_by": user_id,
        })

    # ── Purchase order ──────────────────────────────────────────────
    prices_df = read_table("prices")
    order_rows = [r for r in submit_rows if safe_float(r.get("order_qty", 0)) > 0]

    po_id = norm(existing_po_id)
    po_payload: dict | None = None
    pol_payload: list[dict] = []

    if po_id or order_rows:
        is_new_po = not po_id
        if is_new_po and order_rows:
            po_id = allocate_purchase_order_id()

        if po_id:
            status_value = "draft" if order_rows else "cancelled"
            po_payload = {
                "po_id": po_id,
                "stocktake_id": stocktake_id,
                "store_id": store_id,
                "vendor_id": vendor_id,
                "po_date": str(record_date),
                "order_date": str(record_date),
                "expected_date": str(delivery_date),
                "delivery_date": str(delivery_date),
                "status": status_value,
                "created_at": now,
                "created_by": user_id,
                "updated_at": now,
                "updated_by": user_id,
            }

            existing_pol_id_map = get_existing_po_line_id_map(existing_po_id)
            existing_qty_map, existing_unit_map = get_existing_order_maps(po_id)

            target_item_ids = {
                norm(r.get("item_id", "")) for r in submit_rows if norm(r.get("item_id", ""))
            }
            existing_line_item_ids = {
                norm(k)
                for k in list(existing_qty_map.keys()) + list(existing_unit_map.keys())
                if norm(k)
            }

            items_for_lines = [
                r for r in submit_rows
                if norm(r.get("item_id", "")) in target_item_ids
                and (
                    safe_float(r.get("order_qty", 0)) > 0
                    or norm(r.get("item_id", "")) in existing_line_item_ids
                )
            ]

            new_pol_item_ids = [
                norm(r.get("item_id", ""))
                for r in items_for_lines
                if norm(r.get("item_id", "")) not in existing_pol_id_map
            ]
            new_pol_ids = allocate_many_ids("purchase_order_lines", len(new_pol_item_ids))
            new_pol_id_map = dict(zip(new_pol_item_ids, new_pol_ids))

            for r in items_for_lines:
                item_id = norm(r.get("item_id", ""))
                order_qty = safe_float(r.get("order_qty", 0))
                order_unit = norm(r.get("order_unit", ""))
                item_name = r.get("item_name", "")

                if order_qty > 0:
                    try:
                        order_base_qty, order_base_unit = convert_to_base(
                            item_id=item_id,
                            qty=order_qty,
                            from_unit=order_unit,
                            items_df=vendor_items,
                            conversions_df=conversions_df,
                            as_of_date=record_date,
                        )
                    except Exception as e:
                        raise UserDisplayError(
                            f"{item_name} order conversion failed: {e}"
                        )

                    base_unit_cost = get_base_unit_cost(
                        item_id=item_id,
                        target_date=record_date,
                        items_df=vendor_items,
                        prices_df=prices_df,
                        conversions_df=conversions_df,
                    )
                    # 無有效價格（None / NaN / <=0）一律安全寫入，不阻擋送出
                    _buc = safe_float(base_unit_cost)
                    if _buc > 0:
                        line_amount = round(float(order_base_qty) * _buc, 1)
                        order_unit_price = (
                            round(line_amount / float(order_qty), 4) if float(order_qty) > 0 else 0
                        )
                    else:
                        line_amount = 0
                        order_unit_price = 0
                else:
                    order_base_qty = 0
                    order_base_unit = ""
                    line_amount = 0
                    order_unit_price = 0
                    if not order_unit:
                        order_unit = norm(existing_unit_map.get(item_id, ""))

                line_id = existing_pol_id_map.get(item_id) or new_pol_id_map.get(item_id, "")
                pol_payload.append({
                    "po_line_id": line_id,
                    "po_id": po_id,
                    "store_id": store_id,
                    "vendor_id": vendor_id,
                    "item_id": item_id,
                    "item_name": item_name,
                    "qty": order_qty,
                    "order_qty": order_qty,
                    "unit_id": order_unit,
                    "order_unit": order_unit,
                    "base_qty": round(order_base_qty, 3),
                    "base_unit": order_base_unit,
                    "unit_price": order_unit_price,
                    "amount": line_amount,
                    "delivery_date": str(delivery_date),
                    "created_at": now,
                    "created_by": user_id,
                    "updated_at": now,
                    "updated_by": user_id,
                })

    # ── Audit logs ──────────────────────────────────────────────────
    ts_suffix = pd.Timestamp.now().strftime("%Y%m%d%H%M%S%f")
    audit_logs: list[dict] = [{
        "audit_id": f"AUDIT_{ts_suffix}_ST",
        "ts": now,
        "user_id": user_id,
        "action": "update_stocktake" if existing_stocktake_id else "create_stocktake",
        "table_name": "stocktakes",
        "entity_id": stocktake_id,
        "before_json": {},
        "after_json": {},
        "note": f"store={store_id}, vendor={vendor_id}, date={record_date}",
    }]
    if po_id:
        audit_logs.append({
            "audit_id": f"AUDIT_{ts_suffix}_PO",
            "ts": now,
            "user_id": user_id,
            "action": "update_purchase_order" if existing_po_id else "create_purchase_order",
            "table_name": "purchase_orders",
            "entity_id": po_id,
            "before_json": {},
            "after_json": {},
            "note": (
                f"store={store_id}, vendor={vendor_id}, "
                f"order_date={record_date}, delivery_date={delivery_date}"
            ),
        })

    _payload = {
        "stocktake": stocktake_payload,
        "stocktake_lines": stl_payload,
        "purchase_order": po_payload,
        "purchase_order_lines": pol_payload,
        "audit_logs": audit_logs,
        "_meta": {
            "stocktake_id": stocktake_id,
            "po_id": po_id or "",
        },
    }
    return _sanitize_payload(_payload)
