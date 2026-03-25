from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import pandas as pd


def _norm(v) -> str:
    return str(v).strip() if v is not None else ""


def _safe_float(v, default: float = 0.0) -> float:
    try:
        if v is None or str(v).strip() == "":
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    text = str(v).strip().lower()
    return text in {"true", "1", "yes", "y", "是"}


def _parse_date(v) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()

    text = str(v).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return None

    try:
        return pd.to_datetime(text).date()
    except Exception:
        return None


def _now_ts() -> str:
    return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")


def _clean_option_list(values: list) -> list[str]:
    out = []
    for x in values:
        text = str(x).strip()
        if not text:
            continue
        if text.lower() in {"nan", "none", "nat"}:
            continue
        out.append(text)
    return sorted(list(dict.fromkeys(out)))


def _get_active_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if "is_active" in df.columns:
        return df[df["is_active"].apply(_to_bool)].copy()
    return df.copy()


def _label_store(r) -> str:
    name = _norm(r.get("store_name_zh", "")) or _norm(r.get("store_name", ""))
    sid = _norm(r.get("store_id", ""))
    return name if name else sid


def _label_vendor(r) -> str:
    name = _norm(r.get("vendor_name", ""))
    vid = _norm(r.get("vendor_id", ""))
    return name if name else vid


def _item_display_name(r) -> str:
    return _norm(r.get("item_name_zh", "")) or _norm(r.get("item_name", ""))


def _sort_items_for_operation(df: pd.DataFrame) -> pd.DataFrame:
    """
    作業頁品項排序規則：
    1. 若有 display_order，優先依 display_order 排。
    2. 若沒有 display_order，改依 item_id 的流水序號排，避免被品項名稱影響順序。
    3. 若 item_id 無法拆出數字，最後才用顯示名稱當備援排序。
    """
    if df is None or df.empty:
        return df

    work = df.copy()
    work["_display_name"] = work.apply(_item_display_name, axis=1)

    if "display_order" in work.columns:
        work["_display_order_num"] = pd.to_numeric(work["display_order"], errors="coerce").fillna(999999)
        work = work.sort_values(["_display_order_num", "_display_name"], ascending=[True, True])
        return work

    work["_item_id_sort"] = work.get("item_id", "").astype(str).str.extract(r"(\d+)$", expand=False)
    work["_item_id_sort"] = pd.to_numeric(work["_item_id_sort"], errors="coerce").fillna(999999)
    work = work.sort_values(["_item_id_sort", "_display_name"], ascending=[True, True])
    return work.drop(columns=["_item_id_sort", "_display_name"], errors="ignore")


def _status_hint(total_stock: float, daily_avg: float, suggest_qty: float) -> str:
    total_stock = _safe_float(total_stock)
    daily_avg = _safe_float(daily_avg)
    suggest_qty = _safe_float(suggest_qty)

    if daily_avg > 0 and total_stock < daily_avg:
        return "🔴"
    if suggest_qty > 0 and total_stock < suggest_qty:
        return "🟡"
    return ""


__all__ = [
    "_clean_option_list",
    "_get_active_df",
    "_item_display_name",
    "_label_store",
    "_label_vendor",
    "_norm",
    "_now_ts",
    "_parse_date",
    "_safe_float",
    "_sort_items_for_operation",
    "_status_hint",
    "_to_bool",
]
