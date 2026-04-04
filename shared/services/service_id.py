from __future__ import annotations

from datetime import datetime

from shared.services.id_allocation import allocate_ids


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
    return allocate_ids_map({"users": 1})["users"][0]


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


def allocate_adjustment_id() -> str:
    return allocate_single_id("stock_adjustments")


def allocate_transfer_id() -> str:
    return allocate_single_id("stock_transfers")


def allocate_transfer_line_ids(count: int) -> list[str]:
    return allocate_many_ids("stock_transfer_lines", count)


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
    "allocate_adjustment_id",
    "allocate_transfer_id",
    "allocate_transfer_line_ids",
]
