from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from shared.services.service_order_core import get_active_df, label_store, label_vendor, read_order_table
from shared.utils.common_helpers import _sort_items_for_operation
from operations.logic.order_decision import build_item_decision_data
from operations.logic.order_query import (
    find_existing_operation_ids,
    get_existing_order_maps,
    get_existing_stock_map,
    load_order_page_tables,
    load_selector_tables,
)


def weekday_option_from_date(
    target_date: date | None,
    weekday_options: list[str],
    fallback: date | None = None,
) -> str:
    ref = target_date or fallback or date.today()
    return weekday_options[ref.weekday()]


def delivery_date_from_weekday(
    record_date: date,
    weekday_option: str,
    weekday_options: list[str],
) -> date:
    text = str(weekday_option or "").strip()
    if text not in weekday_options:
        alt_text = text.replace("週", "星期")
        if alt_text in weekday_options:
            text = alt_text
        else:
            return record_date

    target_weekday = weekday_options.index(text)
    current_weekday = record_date.weekday()
    delta = target_weekday - current_weekday
    if delta < 0:
        delta += 7
    return record_date + timedelta(days=delta)


def is_initial_stocktake(store_id: str, stocktakes_df: pd.DataFrame) -> bool:
    if stocktakes_df.empty or "store_id" not in stocktakes_df.columns:
        return True

    store_stocktakes = stocktakes_df[
        stocktakes_df["store_id"].astype(str).str.strip() == str(store_id).strip()
    ]
    return len(store_stocktakes) == 0


def get_active_vendor_items(items_df: pd.DataFrame, vendor_id: str) -> pd.DataFrame:
    if items_df.empty or "default_vendor_id" not in items_df.columns:
        return pd.DataFrame()

    vendor_items = items_df[
        items_df["default_vendor_id"].astype(str).str.strip() == str(vendor_id).strip()
    ].copy()
    vendor_items = _sort_items_for_operation(vendor_items)  # 二次保護：確保 item_id ASC
    return vendor_items.reset_index(drop=True)



def build_order_edit_caption(existing_ids: dict, record_date: date) -> str:
    if not existing_ids:
        return ""

    edit_lines = [f"作業日期：{record_date}"]
    if existing_ids.get("stocktake_id"):
        edit_lines.append(f"盤點單：{existing_ids.get('stocktake_id')}")
    if existing_ids.get("po_id"):
        edit_lines.append(f"叫貨單：{existing_ids.get('po_id')}")
    if existing_ids.get("delivery_date"):
        edit_lines.append(f"到貨日：{existing_ids.get('delivery_date')}")
    return " / ".join(edit_lines)


def build_order_reference_display_df(ref_df: pd.DataFrame, fmt_qty_with_unit) -> pd.DataFrame:
    if ref_df.empty:
        return pd.DataFrame()

    display_df = ref_df.copy()
    display_df["上次叫貨量"] = display_df.apply(
        lambda row: fmt_qty_with_unit(row["last_order_display"], row["last_order_unit"]),
        axis=1,
    )
    display_df["近期待用量"] = display_df.apply(
        lambda row: fmt_qty_with_unit(row["period_usage_display"], row["stock_unit"]),
        axis=1,
    )
    return display_df[["item_name", "上次叫貨量", "近期待用量"]].rename(columns={"item_name": "品項"})


def build_order_item_cards_view_model(vendor_items: pd.DataFrame, item_meta: dict, fmt_qty_with_unit) -> list[dict]:
    cards: list[dict] = []

    for _, row in vendor_items.iterrows():
        item_id = str(row.get("item_id", "")).strip()
        meta = item_meta[item_id]

        daily_avg_value = float(meta["daily_avg"])
        suggest_qty_value = float(meta["suggest_qty"])

        if daily_avg_value > 0:
            coverage_days = round(suggest_qty_value / daily_avg_value, 1)
            coverage_days_display = f"{coverage_days:g}天"
            if coverage_days < 3:
                priority_class = "priority-red"
                suggest_class = "suggest-red"
                coverage_status = "🔴 不足"
            elif coverage_days < 5:
                priority_class = "priority-yellow"
                suggest_class = "suggest-yellow"
                coverage_status = "🟡 觀察"
            else:
                priority_class = "priority-green"
                suggest_class = "suggest-green"
                coverage_status = "🟢 正常"
        else:
            coverage_days_display = "-"
            priority_class = "priority-red"
            suggest_class = "suggest-red"
            coverage_status = "🔴 無日均"

        info_parts = [
            f"日均：{meta['daily_avg']:g}",
            f"<span class='suggest-text {suggest_class}'>建議：{fmt_qty_with_unit(meta['suggest_qty'], meta['stock_unit'])}</span>",
            f"<span class='price-text'>價格：{meta['price']:g}</span>",
        ]
        if meta["status_hint"]:
            info_parts.append(meta["status_hint"])

        cards.append({
            "item_id": item_id,
            "item_name": meta["item_name"],
            "priority_class": priority_class,
            "info_html": "　".join(info_parts),
            "coverage_text": f"庫存合計：{fmt_qty_with_unit(meta['total_stock_display'], meta['stock_unit'])}",
            "stock_unit": meta["stock_unit"],
            "current_stock_qty": float(meta["current_stock_qty"]),
            "existing_order_qty": float(meta["existing_order_qty"]),
            "orderable_unit_options": meta["orderable_unit_options"],
            "existing_order_unit": meta["existing_order_unit"],
            "price": float(meta["price"]),
        })

    return cards

def get_store_selection_view_model() -> dict:
    selector_tables = load_selector_tables()
    stores_df = get_active_df(selector_tables["stores"])
    login_role_id = str(st.session_state.get("login_role_id", "")).strip().lower()
    login_store_scope = str(st.session_state.get("login_store_scope", "")).strip()

    error_message = ""
    if not stores_df.empty:
        stores_df = stores_df.copy()
        if login_role_id not in ["owner", "admin", "test_admin"]:
            if not login_store_scope or login_store_scope == "ALL":
                error_message = "目前帳號缺少可用門市範圍設定。"
                stores_df = stores_df.iloc[0:0].copy()
            else:
                stores_df = stores_df[
                    stores_df["store_id"].astype(str).str.strip() == login_store_scope
                ].copy()
                if stores_df.empty:
                    error_message = "目前帳號的 store_scope 無法對應到有效門市。"

    if not stores_df.empty:
        if "store_id" in stores_df.columns:
            stores_df = stores_df.sort_values("store_id", ascending=True).reset_index(drop=True)
        stores_df["store_label"] = stores_df.apply(label_store, axis=1)

    return {
        "stores_df": stores_df,
        "error_message": error_message,
    }


def get_vendor_selection_view_model(record_date: date, store_id: str) -> dict:
    selector_tables = load_selector_tables()
    vendors_df = get_active_df(selector_tables["vendors"])
    items_df = get_active_df(selector_tables["items"])

    vendors = pd.DataFrame()
    if not vendors_df.empty and not items_df.empty:
        item_vendor_ids = set(
            items_df.get("default_vendor_id", pd.Series(dtype=str))
            .astype(str)
            .str.strip()
        )
        vendors = vendors_df[
            vendors_df["vendor_id"].astype(str).str.strip().isin(item_vendor_ids)
        ].copy()
        if not vendors.empty:
            vendors["vendor_label"] = vendors.apply(label_vendor, axis=1)
            vendors = vendors.sort_values(by=["vendor_label"], ascending=True).reset_index(
                drop=True
            )

    return {
        "record_date": record_date,
        "store_id": store_id,
        "vendors_df": vendors_df,
        "items_df": items_df,
        "vendors": vendors,
    }


def build_order_entry_view_model(
    *,
    store_id: str,
    vendor_id: str,
    record_date: date,
    weekday_options: list[str],
) -> dict:
    initial_stocktakes_df = read_order_table("stocktakes")
    is_initial_stock = is_initial_stocktake(store_id, initial_stocktakes_df)

    page_tables = load_order_page_tables()
    items_df = get_active_df(page_tables["items"])
    prices_df = page_tables["prices"]
    conversions_df = get_active_df(page_tables["unit_conversions"])
    stocktakes_df = page_tables["stocktakes"]
    stocktake_lines_df = page_tables["stocktake_lines"]

    has_items = not items_df.empty
    has_default_vendor_column = "default_vendor_id" in items_df.columns if has_items else False
    vendor_items = (
        get_active_vendor_items(items_df, vendor_id)
        if has_items and has_default_vendor_column
        else pd.DataFrame()
    )

    existing_ids = find_existing_operation_ids(
        store_id=store_id,
        vendor_id=vendor_id,
        record_date=record_date,
    )
    existing_stock_map = get_existing_stock_map(existing_ids.get("stocktake_id", ""))
    existing_order_qty_map, existing_order_unit_map = get_existing_order_maps(
        existing_ids.get("po_id", "")
    )
    existing_delivery_option = weekday_option_from_date(
        existing_ids.get("delivery_date"),
        weekday_options,
        record_date + timedelta(days=1),
    )

    decision = {
        "item_meta": {},
        "ref_df": pd.DataFrame(),
    }
    if not vendor_items.empty:
        decision = build_item_decision_data(
            vendor_items=vendor_items,
            prices_df=prices_df,
            conversions_df=conversions_df,
            stocktakes_df=stocktakes_df,
            stocktake_lines_df=stocktake_lines_df,
            store_id=store_id,
            vendor_id=vendor_id,
            record_date=record_date,
            existing_stock_map=existing_stock_map,
            existing_order_qty_map=existing_order_qty_map,
            existing_order_unit_map=existing_order_unit_map,
        )

    return {
        "is_initial_stock": is_initial_stock,
        "items_df_empty": items_df.empty,
        "items_missing_default_vendor_id": has_items and not has_default_vendor_column,
        "vendor_items": vendor_items,
        "page_tables": page_tables,
        "conversions_df": conversions_df,
        "existing_ids": existing_ids,
        "existing_delivery_option": existing_delivery_option,
        "is_edit_mode": bool(existing_ids.get("stocktake_id") or existing_ids.get("po_id")),
        "item_meta": decision["item_meta"],
        "ref_df": decision["ref_df"],
    }
