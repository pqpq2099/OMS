# ============================================================
# ORIVIA OMS - Core Logic
# 最小骨架版：先放共用邏輯與未來擴充入口
# ============================================================

from __future__ import annotations

from typing import Any


def _norm(value: Any) -> str:
    """把值轉成乾淨字串。"""
    if value is None:
        return ""
    return str(value).strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    """安全轉 float。"""
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def calculate_suggested_qty(daily_avg: float, multiplier: float = 1.5) -> float:
    """建議量基本公式。"""
    return round(_safe_float(daily_avg) * _safe_float(multiplier, 1.5), 1)


def calculate_period_consumption(
    previous_stock: float,
    period_purchase: float,
    current_stock: float,
) -> float:
    """期間消耗 = 上次庫存 + 期間進貨 - 這次庫存"""
    return round(
        _safe_float(previous_stock)
        + _safe_float(period_purchase)
        - _safe_float(current_stock),
        4,
    )


def calculate_inventory_value(base_qty: float, base_unit_cost: float) -> float:
    """庫存金額 / 成本計算基礎。"""
    return round(_safe_float(base_qty) * _safe_float(base_unit_cost), 4)
