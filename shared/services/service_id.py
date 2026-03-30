from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from shared.services.id_allocation import allocate_ids
from shared.utils.common_helpers import _norm
from shared.services.service_sheet import sheet_bust_cache, sheet_read, sheet_replace_table


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def allocate_ids_map(id_map: dict):
    return allocate_ids(id_map)


def allocate_single_id(sequence_key: str) -> str:
    allocated = allocate_ids_map({sequence_key: 1})
    return allocated[sequence_key][0]


def allocate_many_ids(sequence_key: str, count: int) -> list[str]:
    if int(count or 0) <= 0:
        return []
    allocated = allocate_ids_map({sequence_key: int(count)})
    return list(allocated.get(sequence_key, []))


def allocate_user_id() -> str:
    try:
        return allocate_ids_map({"users": 1})["users"][0]
    except Exception:
        df = sheet_read("id_sequences").copy()
        if df.empty:
            raise ValueError("id_sequences worksheet has no usable data")

        df.columns = [_norm(x) for x in df.columns]
        required = ["key", "env", "prefix", "width", "next_value"]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Missing required column in id_sequences: {col}")

        hit = df[(df["key"].astype(str).str.strip() == "users") & (df["env"].astype(str).str.strip() == "prod")]
        if hit.empty:
            raise ValueError("Cannot find id_sequences row for users/prod")

        idx = hit.index[0]
        prefix = _norm(df.at[idx, "prefix"])
        width = int(pd.to_numeric(df.at[idx, "width"], errors="coerce") or 0)
        next_value = int(pd.to_numeric(df.at[idx, "next_value"], errors="coerce") or 0)
        if not prefix or width <= 0 or next_value <= 0:
            raise ValueError("Invalid users sequence configuration")

        new_user_id = f"{prefix}{str(next_value).zfill(width)}"
        df.at[idx, "next_value"] = str(next_value + 1)
        if "updated_at" in df.columns:
            df.at[idx, "updated_at"] = _now_ts()
        if "updated_by" in df.columns:
            df.at[idx, "updated_by"] = str(st.session_state.get("login_user", "")).strip()

        header = list(df.columns)
        rows = df[header].fillna("").astype(str).values.tolist()
        sheet_replace_table("id_sequences", header, rows)
        sheet_bust_cache()
        return new_user_id


def allocate_purchase_order_id() -> str:
    return allocate_single_id("purchase_orders")


def allocate_purchase_order_line_ids(count: int) -> list[str]:
    return allocate_many_ids("purchase_order_lines", count)


def allocate_stocktake_id() -> str:
    return allocate_single_id("stocktakes")


def allocate_stocktake_line_ids(count: int) -> list[str]:
    return allocate_many_ids("stocktake_lines", count)


def allocate_vendor_id() -> str:
    return allocate_single_id("vendors")


def allocate_unit_id() -> str:
    return allocate_single_id("units")


def allocate_item_id() -> str:
    return allocate_single_id("items")


def allocate_price_id() -> str:
    return allocate_single_id("prices")


def allocate_unit_conversion_id() -> str:
    return allocate_single_id("unit_conversions")


def allocate_store_id() -> str:
    return allocate_single_id("stores")


def allocate_audit_id() -> str:
    return allocate_single_id("audit_logs")


__all__ = [
    "allocate_ids_map",
    "allocate_single_id",
    "allocate_many_ids",
    "allocate_user_id",
    "allocate_vendor_id",
    "allocate_unit_id",
    "allocate_item_id",
    "allocate_price_id",
    "allocate_unit_conversion_id",
    "allocate_store_id",
    "allocate_audit_id",
    "allocate_purchase_order_id",
    "allocate_purchase_order_line_ids",
    "allocate_stocktake_id",
    "allocate_stocktake_line_ids",
]
