# ============================================================
# ORIVIA OMS
# 檔案：services/service_order.py
# 說明：叫貨流程服務層
# 功能：處理叫貨頁所需的商業邏輯、驗證與資料整理。
# 注意：UI 只負責顯示，業務規則盡量放在這裡。
# ============================================================

"""
服務層：叫貨流程服務。
介於 UI 與資料層之間，放叫貨相關業務邏輯。
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import requests
import streamlit as st

from operations.logic import logic_order
from operations.logic.order_decision import build_item_decision_data
from operations.logic.order_validation import validate_order_submission
from operations.logic.order_write import _save_order_entry
from oms_core import _norm, get_table_versions, read_table


_ORDER_PAGE_TABLES = (
    "stores",
    "vendors",
    "items",
    "prices",
    "unit_conversions",
    "stocktakes",
    "stocktake_lines",
    "purchase_orders",
    "purchase_order_lines",
)


def get_store_selection_view_model() -> dict:
    return logic_order.get_store_selection_view_model()


def get_vendor_selection_view_model(*, record_date: date, store_id: str) -> dict:
    return logic_order.get_vendor_selection_view_model(
        record_date=record_date,
        store_id=store_id,
    )


def build_order_entry_view_model(
    *,
    store_id: str,
    vendor_id: str,
    record_date: date,
    weekday_options: list[str],
) -> dict:
    return logic_order.build_order_entry_view_model(
        store_id=store_id,
        vendor_id=vendor_id,
        record_date=record_date,
        weekday_options=weekday_options,
    )


def validate_order_input(
    *,
    submit_rows: list[dict],
    vendor_items: pd.DataFrame,
    conversions_df: pd.DataFrame,
    record_date: date,
    is_initial_stock: bool,
) -> list[str]:
    return validate_order_submission(
        submit_rows=submit_rows,
        vendor_items=vendor_items,
        conversions_df=conversions_df,
        record_date=record_date,
        is_initial_stock=is_initial_stock,
    )


def calculate_order(**kwargs):
    return build_item_decision_data(**kwargs)


def save_order(
    *,
    submit_rows: list[dict],
    vendor_items: pd.DataFrame,
    conversions_df: pd.DataFrame,
    store_id: str,
    vendor_id: str,
    record_date: date,
    delivery_date: date,
    existing_stocktake_id: str,
    existing_po_id: str,
    is_initial_stock: bool,
) -> str:
    return _save_order_entry(
        submit_rows=submit_rows,
        vendor_items=vendor_items,
        conversions_df=conversions_df,
        store_id=store_id,
        vendor_id=vendor_id,
        record_date=record_date,
        delivery_date=delivery_date,
        existing_stocktake_id=existing_stocktake_id,
        existing_po_id=existing_po_id,
        is_initial_stock=is_initial_stock,
    )


def delivery_date_from_weekday(
    record_date: date,
    selected_delivery_weekday: str,
    weekday_options: list[str],
) -> date:
    return logic_order.delivery_date_from_weekday(
        record_date,
        selected_delivery_weekday,
        weekday_options,
    )


def load_order_page_tables() -> dict[str, pd.DataFrame]:
    versions = get_table_versions(_ORDER_PAGE_TABLES)
    cache = st.session_state.get("_order_page_tables_cache")
    if isinstance(cache, dict) and cache.get("versions") == versions:
        data = cache.get("data", {})
        if data:
            return {k: v.copy() for k, v in data.items()}

    data = {name: read_table(name) for name in _ORDER_PAGE_TABLES}
    st.session_state["_order_page_tables_cache"] = {
        "versions": versions,
        "data": {k: v.copy() for k, v in data.items()},
    }
    return {k: v.copy() for k, v in data.items()}


def clear_order_page_tables_cache():
    st.session_state.pop("_order_page_tables_cache", None)


def send_line_message(line_message: str) -> bool:
    try:
        store_id = str(st.session_state.get("store_id", "")).strip()

        channel_access_token = str(
            st.secrets.get("LINE_CHANNEL_ACCESS_TOKEN", "")
        ).strip()

        if not channel_access_token:
            try:
                line_bot_cfg = st.secrets.get("line_bot", {})
                channel_access_token = str(
                    line_bot_cfg.get("channel_access_token", "")
                ).strip()
            except Exception:
                channel_access_token = ""

        group_id = ""

        try:
            line_groups_cfg = st.secrets.get("line_groups", {})
            if store_id:
                group_id = str(line_groups_cfg.get(store_id, "")).strip()
        except Exception:
            group_id = ""

        if not group_id:
            group_id = str(
                st.secrets.get("LINE_GROUP_ID", "")
            ).strip()

        if not channel_access_token:
            st.error(
                "缺少 LINE token，請檢查 Streamlit secrets："
                "LINE_CHANNEL_ACCESS_TOKEN 或 [line_bot].channel_access_token"
            )
            return False

        if not group_id:
            if store_id:
                st.error(
                    f"找不到分店 {store_id} 對應的 LINE 群組，"
                    "請檢查 [line_groups] 或 LINE_GROUP_ID 設定。"
                )
            else:
                st.error("缺少 LINE 群組設定，請檢查 [line_groups] 或 LINE_GROUP_ID。")
            return False

        url = "https://api.line.me/v2/bot/message/push"

        headers = {
            "Authorization": f"Bearer {channel_access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "to": group_id,
            "messages": [
                {
                    "type": "text",
                    "text": line_message,
                }
            ],
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=15,
        )

        if response.status_code == 200:
            return True

        st.error(f"LINE API 錯誤：{response.status_code} / {response.text}")
        return False

    except Exception as exc:
        st.error(f"發送 LINE 時發生錯誤：{exc}")
        return False


def convert_metric_base_to_stock_display_qty(
    *,
    item_id: str,
    qty: float,
    stock_unit: str,
    base_unit: str,
    conversions_df: pd.DataFrame,
    as_of_date: date,
) -> float:
    return logic_order.convert_metric_base_to_stock_display_qty(
        item_id=item_id,
        qty=qty,
        stock_unit=stock_unit,
        base_unit=base_unit,
        conversions_df=conversions_df,
        as_of_date=as_of_date,
    )


def convert_metric_base_to_order_display_qty(
    *,
    item_id: str,
    qty: float,
    order_unit: str,
    base_unit: str,
    conversions_df: pd.DataFrame,
    as_of_date: date,
) -> float:
    return logic_order.convert_metric_base_to_order_display_qty(
        item_id=item_id,
        qty=qty,
        order_unit=order_unit,
        base_unit=base_unit,
        conversions_df=conversions_df,
        as_of_date=as_of_date,
    )


def normalize_text(value) -> str:
    return _norm(value)
