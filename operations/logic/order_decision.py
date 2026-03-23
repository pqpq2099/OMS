from __future__ import annotations

from datetime import date

import pandas as pd

from oms_core import (
    _build_latest_item_metrics_df,
    _clean_option_list,
    _get_latest_price_for_item,
    _get_latest_stock_qty_in_display_unit,
    _item_display_name,
    _norm,
    _safe_float,
    _status_hint,
)
from utils.utils_units import convert_unit


def convert_metric_base_to_stock_display_qty(
    *,
    item_id: str,
    qty: float,
    stock_unit: str,
    base_unit: str,
    conversions_df: pd.DataFrame,
    as_of_date: date,
) -> float:
    qty = _safe_float(qty, 0)
    item_id = _norm(item_id)
    stock_unit = _norm(stock_unit)
    base_unit = _norm(base_unit)

    if not item_id or not stock_unit:
        return round(qty, 1)

    if qty == 0 or stock_unit == base_unit or not base_unit:
        return round(qty, 1)

    try:
        converted = convert_unit(
            item_id=item_id,
            qty=qty,
            from_unit=base_unit,
            to_unit=stock_unit,
            conversions_df=conversions_df,
            as_of_date=as_of_date,
        )
        return round(converted, 1)
    except Exception:
        return round(qty, 1)


def convert_metric_base_to_order_display_qty(
    *,
    item_id: str,
    qty: float,
    order_unit: str,
    base_unit: str,
    conversions_df: pd.DataFrame,
    as_of_date: date,
) -> float:
    qty = _safe_float(qty, 0)
    item_id = _norm(item_id)
    order_unit = _norm(order_unit)
    base_unit = _norm(base_unit)

    if not item_id or not order_unit:
        return round(qty, 1)

    if qty == 0 or order_unit == base_unit or not base_unit:
        return round(qty, 1)

    try:
        converted = convert_unit(
            item_id=item_id,
            qty=qty,
            from_unit=base_unit,
            to_unit=order_unit,
            conversions_df=conversions_df,
            as_of_date=as_of_date,
        )
        return round(converted, 1)
    except Exception:
        return round(qty, 1)


def build_item_decision_data(
    *,
    vendor_items: pd.DataFrame,
    prices_df: pd.DataFrame,
    conversions_df: pd.DataFrame,
    stocktakes_df: pd.DataFrame,
    stocktake_lines_df: pd.DataFrame,
    store_id: str,
    vendor_id: str,
    record_date: date,
    existing_stock_map: dict[str, float],
    existing_order_qty_map: dict[str, float],
    existing_order_unit_map: dict[str, str],
) -> dict:
    latest_metrics_df = _build_latest_item_metrics_df(
        store_id=store_id,
        as_of_date=record_date,
    )

    latest_metrics_map = {}
    if not latest_metrics_df.empty:
        latest_metrics_df = latest_metrics_df.copy()
        if "vendor_id" in latest_metrics_df.columns:
            latest_metrics_df["vendor_id"] = (
                latest_metrics_df["vendor_id"].astype(str).str.strip()
            )
            latest_metrics_df = latest_metrics_df[
                latest_metrics_df["vendor_id"] == str(vendor_id).strip()
            ].copy()
        for _, metric_row in latest_metrics_df.iterrows():
            latest_metrics_map[_norm(metric_row.get("item_id", ""))] = metric_row.to_dict()

    item_meta = {}
    ref_rows = []

    for _, row in vendor_items.iterrows():
        item_id = _norm(row.get("item_id", ""))
        item_name = _item_display_name(row)

        base_unit = _norm(row.get("base_unit", ""))
        stock_unit = _norm(row.get("default_stock_unit", "")) or base_unit
        order_unit = _norm(row.get("default_order_unit", "")) or base_unit

        price = _get_latest_price_for_item(prices_df, item_id, record_date)

        current_stock_qty = existing_stock_map.get(item_id)
        if current_stock_qty is None:
            current_stock_qty = _get_latest_stock_qty_in_display_unit(
                stocktakes_df=stocktakes_df,
                stocktake_lines_df=stocktake_lines_df,
                items_df=vendor_items,
                conversions_df=conversions_df,
                store_id=store_id,
                item_id=item_id,
                display_unit=stock_unit,
                as_of_date=record_date,
            )

        metric = latest_metrics_map.get(item_id, {})
        period_purchase = _safe_float(metric.get("近30日叫貨量", 0))
        period_usage = _safe_float(metric.get("近30日用量", 0))
        last_order_qty = _safe_float(metric.get("上次叫貨量", 0))
        daily_avg = _safe_float(metric.get("日平均用量", 0))
        total_stock_ref = _safe_float(metric.get("總庫存量", 0))
        suggest_qty = round(daily_avg * 1.5, 1)
        status_hint = _status_hint(total_stock_ref, daily_avg, suggest_qty)

        total_stock_display = convert_metric_base_to_stock_display_qty(
            item_id=item_id,
            qty=total_stock_ref,
            stock_unit=stock_unit,
            base_unit=base_unit,
            conversions_df=conversions_df,
            as_of_date=record_date,
        )
        suggest_display = convert_metric_base_to_stock_display_qty(
            item_id=item_id,
            qty=suggest_qty,
            stock_unit=stock_unit,
            base_unit=base_unit,
            conversions_df=conversions_df,
            as_of_date=record_date,
        )
        period_usage_display = convert_metric_base_to_stock_display_qty(
            item_id=item_id,
            qty=period_usage,
            stock_unit=stock_unit,
            base_unit=base_unit,
            conversions_df=conversions_df,
            as_of_date=record_date,
        )

        last_order_ref = last_order_qty if last_order_qty > 0 else period_purchase
        last_order_display = convert_metric_base_to_order_display_qty(
            item_id=item_id,
            qty=last_order_ref,
            order_unit=order_unit,
            base_unit=base_unit,
            conversions_df=conversions_df,
            as_of_date=record_date,
        )

        orderable_units_raw = _norm(row.get("orderable_units", ""))
        orderable_unit_options = [
            unit.strip() for unit in orderable_units_raw.split(",") if unit.strip()
        ]
        if order_unit and order_unit not in orderable_unit_options:
            orderable_unit_options.insert(0, order_unit)
        if not orderable_unit_options:
            orderable_unit_options = [order_unit] if order_unit else [base_unit]
        orderable_unit_options = _clean_option_list(orderable_unit_options)

        item_meta[item_id] = {
            "item_id": item_id,
            "item_name": item_name,
            "base_unit": base_unit,
            "stock_unit": stock_unit,
            "order_unit": order_unit,
            "orderable_unit_options": orderable_unit_options,
            "price": round(price, 1),
            "current_stock_qty": round(current_stock_qty, 1),
            "total_stock_ref": round(total_stock_ref, 1),
            "total_stock_display": round(total_stock_display, 1),
            "daily_avg": round(daily_avg, 1),
            "period_usage_display": round(period_usage_display, 1),
            "last_order_display": round(last_order_display, 1),
            "suggest_qty": suggest_qty,
            "suggest_display": round(suggest_display, 1),
            "status_hint": status_hint,
            "existing_order_qty": round(
                _safe_float(existing_order_qty_map.get(item_id, 0)), 1
            ),
            "existing_order_unit": _norm(existing_order_unit_map.get(item_id, ""))
            or order_unit,
        }

        if last_order_ref > 0 or period_usage > 0 or current_stock_qty > 0:
            ref_rows.append(
                {
                    "item_name": item_name,
                    "last_order_display": round(last_order_display, 1),
                    "last_order_unit": order_unit,
                    "period_usage_display": round(period_usage_display, 1),
                    "stock_unit": stock_unit,
                }
            )

    ref_df = pd.DataFrame(ref_rows) if ref_rows else pd.DataFrame()
    if not ref_df.empty:
        ref_df = ref_df.sort_values(["item_name"]).reset_index(drop=True)

    return {
        "item_meta": item_meta,
        "ref_df": ref_df,
    }
