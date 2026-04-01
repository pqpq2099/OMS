from __future__ import annotations

from datetime import date
import copy

import numpy as np
import pandas as pd

from shared.utils.utils_units import convert_to_base, convert_unit, get_base_unit
from shared.utils.common_helpers import (
    _get_active_df,
    _item_display_name,
    _label_store,
    _label_vendor,
    _norm,
    _parse_date,
    _safe_float,
    _to_bool,
)
from shared.services.data_backend import (
    _session_df_cache_get,
    _session_df_cache_set,
    _table_versions_signature,
    read_table,
)


def _parse_vendor_id_from_note(note: str) -> str:
    text = _norm(note)
    if "vendor=" not in text:
        return ""
    try:
        return text.split("vendor=", 1)[1].strip()
    except Exception:
        return ""

def _coalesce_columns(df: pd.DataFrame, candidates: list[str], default="") -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype="object")

    result = pd.Series([pd.NA] * len(df), index=df.index, dtype="object")

    for col in candidates:
        if col in df.columns:
            s = df[col].copy()
            s = s.where(~pd.isna(s), pd.NA)

            if s.dtype == "object":
                s = s.apply(lambda x: pd.NA if str(x).strip() == "" else x)

            result = result.combine_first(s)

    if default != "":
        result = result.fillna(default)

    return result


def _normalize_key_series(series: pd.Series) -> pd.Series:
    if series is None:
        return pd.Series(dtype="object")
    return series.astype(str).str.strip()


def _get_derived_cache(cache_key: str, table_names: tuple[str, ...]) -> pd.DataFrame | None:
    signature = _table_versions_signature(table_names)
    return _session_df_cache_get(cache_key, signature)


def _set_derived_cache(cache_key: str, table_names: tuple[str, ...], df: pd.DataFrame) -> pd.DataFrame:
    signature = _table_versions_signature(table_names)
    _session_df_cache_set(cache_key, signature, df)
    return df


def _build_label_map(df: pd.DataFrame, key_col: str, label_col: str, label_func, fallback_col: str | None = None) -> dict:
    if df.empty or key_col not in df.columns:
        return {}
    work = df.copy()
    work[key_col] = _normalize_key_series(work[key_col])
    work[label_col] = work.apply(label_func, axis=1)
    mapping = dict(zip(work[key_col], work[label_col]))
    if fallback_col and fallback_col in work.columns:
        fallback = work[[key_col, fallback_col]].copy()
        fallback[fallback_col] = fallback[fallback_col].astype(str)
        for key, value in zip(fallback[key_col], fallback[fallback_col]):
            mapping.setdefault(key, value)
    return mapping


def _convert_base_qty_with_cache(
    item_id: str,
    base_qty: float,
    base_unit: str,
    display_unit: str,
    conversions_df: pd.DataFrame,
    as_of_date: date | None,
    factor_cache: dict,
) -> float:
    if base_qty == 0:
        return 0.0
    if not base_unit or not display_unit or base_unit == display_unit:
        return float(base_qty)

    cache_key = (str(item_id).strip(), str(base_unit).strip(), str(display_unit).strip(), str(as_of_date or ""))
    factor = factor_cache.get(cache_key)
    if factor is None:
        try:
            factor = float(
                convert_unit(
                    item_id=item_id,
                    qty=1.0,
                    from_unit=base_unit,
                    to_unit=display_unit,
                    conversions_df=conversions_df,
                    as_of_date=as_of_date,
                )
            )
        except Exception:
            factor = None
        factor_cache[cache_key] = factor

    if factor is None:
        return float(base_qty)
    return float(base_qty) * factor



def _build_preferred_label_map(df: pd.DataFrame, key_col: str, label_cols: list[str], *, empty_default: str | None = None) -> dict:
    if df.empty or key_col not in df.columns:
        return {}
    work = pd.DataFrame({key_col: _normalize_key_series(df[key_col])})
    label_series = pd.Series(pd.NA, index=df.index, dtype="object")
    for col in label_cols:
        if col in df.columns:
            src = df[col].astype("object")
            src = src.where(~pd.isna(src), pd.NA)
            src = src.where(src.astype(str).str.strip() != "", pd.NA)
            label_series = label_series.combine_first(src)
    if empty_default is not None:
        label_series = label_series.fillna(empty_default)
    work["__label"] = label_series.astype("object")
    work = work.drop_duplicates(subset=[key_col], keep="first")
    return dict(zip(work[key_col], work["__label"]))


def _compute_display_qty_series(
    item_ids: pd.Series,
    base_qtys: pd.Series,
    base_units: pd.Series,
    display_units: pd.Series,
    as_of_dates: pd.Series,
    conversions_df: pd.DataFrame,
    *,
    round_digits: int = 1,
) -> pd.Series:
    if len(base_qtys) == 0:
        return pd.Series(dtype="float64")

    work = pd.DataFrame({
        "item_id": item_ids.astype(str).str.strip(),
        "base_qty": pd.to_numeric(base_qtys, errors="coerce").fillna(0.0),
        "base_unit": base_units.astype(str).str.strip(),
        "display_unit": display_units.astype(str).str.strip(),
        "as_of_date": as_of_dates,
    })

    mask_direct = (
        work["base_qty"].eq(0)
        | work["base_unit"].eq("")
        | work["display_unit"].eq("")
        | work["base_unit"].eq(work["display_unit"])
    )
    out = work["base_qty"].astype(float).copy()
    factor_cache: dict = {}

    pending = work.loc[~mask_direct, ["item_id", "base_qty", "base_unit", "display_unit", "as_of_date"]].copy()
    if not pending.empty:
        pending["conv_key"] = list(zip(
            pending["item_id"],
            pending["base_unit"],
            pending["display_unit"],
            pending["as_of_date"],
        ))
        qty_map: dict = {}
        unique_pending = pending.drop_duplicates(subset=["conv_key"], keep="first")
        for row in unique_pending.itertuples(index=False):
            key = getattr(row, "conv_key")
            qty_map[key] = _convert_base_qty_with_cache(
                item_id=row.item_id,
                base_qty=float(row.base_qty),
                base_unit=row.base_unit,
                display_unit=row.display_unit,
                conversions_df=conversions_df,
                as_of_date=row.as_of_date,
                factor_cache=factor_cache,
            )
        out.loc[pending.index] = pending["conv_key"].map(qty_map).astype(float)

    return out.round(round_digits)
def get_base_unit_cost(item_id, target_date, items_df, prices_df, conversions_df):
    if items_df.empty or prices_df.empty:
        return None

    item_row = items_df[items_df["item_id"].astype(str).str.strip() == str(item_id).strip()]
    if item_row.empty:
        return None

    base_unit = str(item_row.iloc[0].get("base_unit", "")).strip()
    if not base_unit:
        return None

    price_rows = prices_df.copy()
    price_rows = price_rows[
        price_rows["item_id"].astype(str).str.strip() == str(item_id).strip()
    ]

    if "is_active" in price_rows.columns:
        price_rows = price_rows[
            price_rows["is_active"].apply(
                lambda x: str(x).strip() in ["1", "True", "true", "YES", "yes", "是"]
            )
        ]

    if price_rows.empty:
        return None

    price_rows["__eff"] = price_rows["effective_date"].apply(_parse_date)
    price_rows["__end"] = price_rows["end_date"].apply(_parse_date)

    price_rows = price_rows[
        (price_rows["__eff"].isna() | (price_rows["__eff"] <= target_date))
        & (price_rows["__end"].isna() | (price_rows["__end"] >= target_date))
    ]

    if price_rows.empty:
        return None

    price_rows = price_rows.sort_values("__eff", ascending=True)
    price_row = price_rows.iloc[-1]

    unit_price = _safe_float(price_row.get("unit_price", 0))
    price_unit = str(price_row.get("price_unit", "")).strip()

    if unit_price == 0:
        return None

    if price_unit == base_unit or price_unit == "":
        return unit_price

    # price_unit 可能以 unit_name 儲存（如 "條"），base_unit 以 unit_id 儲存（如 "UNIT_000005"）
    # 嘗試透過 units 表正規化後再比對，避免同單位不同表示法時走入 conversion 路徑
    try:
        _units = read_table("units")
        if not _units.empty and {"unit_id", "unit_name"}.issubset(_units.columns):
            _name_to_id = {
                str(n).strip(): str(i).strip()
                for n, i in zip(_units["unit_name"], _units["unit_id"])
                if str(n).strip() and str(i).strip()
            }
            if _name_to_id.get(price_unit, "") == base_unit:
                return unit_price
    except Exception:
        pass

    conv = conversions_df[
        (conversions_df["item_id"].astype(str).str.strip() == str(item_id).strip())
        & (conversions_df["from_unit"].astype(str).str.strip() == price_unit)
        & (conversions_df["to_unit"].astype(str).str.strip() == base_unit)
    ]

    if conv.empty:
        return None

    ratio = _safe_float(conv.iloc[0].get("ratio", 0))
    if ratio == 0:
        return None

    return round(unit_price / ratio, 4)

def _get_latest_price_for_item(prices_df: pd.DataFrame, item_id: str, target_date: date) -> float:
    if prices_df.empty or "item_id" not in prices_df.columns:
        return 0.0

    tmp = prices_df.copy()
    for col in ["effective_date", "end_date", "unit_price", "is_active"]:
        if col not in tmp.columns:
            tmp[col] = ""

    tmp = tmp[tmp["item_id"].astype(str).str.strip() == str(item_id).strip()].copy()
    if tmp.empty:
        return 0.0

    tmp["__eff"] = tmp["effective_date"].apply(_parse_date)
    tmp["__end"] = tmp["end_date"].apply(_parse_date)
    tmp["__active"] = tmp["is_active"].apply(lambda x: (str(x).strip() == "" or _to_bool(x)))
    tmp["unit_price"] = pd.to_numeric(tmp["unit_price"], errors="coerce").fillna(0)

    tmp = tmp[tmp["__active"]]
    tmp = tmp[
        (tmp["__eff"].isna() | (tmp["__eff"] <= target_date))
        & (tmp["__end"].isna() | (tmp["__end"] >= target_date))
    ].copy()

    if tmp.empty:
        return 0.0

    tmp = tmp.sort_values("__eff", ascending=True)
    return float(tmp.iloc[-1]["unit_price"])

def _get_last_po_summary(
    po_df: pd.DataFrame,
    pol_df: pd.DataFrame,
    store_id: str,
    vendor_id: str,
    item_id: str,
):
    if po_df.empty or pol_df.empty:
        return 0.0, ""

    need_po = {"po_id", "store_id", "vendor_id", "order_date"}
    need_pol = {"po_id", "item_id"}
    if not need_po.issubset(set(po_df.columns)) or not need_pol.issubset(set(pol_df.columns)):
        return 0.0, ""

    po = po_df.copy()
    pol = pol_df.copy()

    po["po_id"] = po["po_id"].astype(str).str.strip()
    pol["po_id"] = pol["po_id"].astype(str).str.strip()
    pol["item_id"] = pol["item_id"].astype(str).str.strip()

    po = po[
        (po["store_id"].astype(str).str.strip() == str(store_id).strip())
        & (po["vendor_id"].astype(str).str.strip() == str(vendor_id).strip())
    ].copy()

    if po.empty:
        return 0.0, ""

    merged = pol.merge(po[["po_id", "order_date"]], on="po_id", how="inner")
    merged = merged[merged["item_id"] == str(item_id).strip()].copy()
    if merged.empty:
        return 0.0, ""

    merged["__date"] = merged["order_date"].apply(_parse_date)
    merged = merged.sort_values("__date", ascending=True)
    latest = merged.iloc[-1].to_dict()

    qty = _safe_float(latest.get("order_qty", latest.get("qty", 0)))
    unit = _norm(latest.get("order_unit", latest.get("unit_id", "")))
    return qty, unit

def _get_latest_stock_qty_in_display_unit(
    stocktakes_df: pd.DataFrame,
    stocktake_lines_df: pd.DataFrame,
    items_df: pd.DataFrame,
    conversions_df: pd.DataFrame,
    store_id: str,
    item_id: str,
    display_unit: str,
    as_of_date: date | None = None,
):
    if stocktakes_df.empty or stocktake_lines_df.empty:
        return 0.0

    need_st = {"stocktake_id", "store_id", "stocktake_date"}
    need_stl = {"stocktake_id", "item_id"}
    if not need_st.issubset(set(stocktakes_df.columns)) or not need_stl.issubset(set(stocktake_lines_df.columns)):
        return 0.0

    stx = stocktakes_df.copy()
    stl = stocktake_lines_df.copy()

    stx["stocktake_id"] = stx["stocktake_id"].astype(str).str.strip()
    stl["stocktake_id"] = stl["stocktake_id"].astype(str).str.strip()
    stl["item_id"] = stl["item_id"].astype(str).str.strip()

    stx = stx[stx["store_id"].astype(str).str.strip() == str(store_id).strip()].copy()
    if stx.empty:
        return 0.0

    merged = stl.merge(stx[["stocktake_id", "stocktake_date"]], on="stocktake_id", how="inner")
    merged = merged[merged["item_id"] == str(item_id).strip()].copy()
    if merged.empty:
        return 0.0

    merged["__date"] = merged["stocktake_date"].apply(_parse_date)
    if as_of_date is not None:
        merged = merged[merged["__date"].notna() & (merged["__date"] <= as_of_date)].copy()
        if merged.empty:
            return 0.0
    merged = merged.sort_values("__date", ascending=True)
    latest = merged.iloc[-1].to_dict()

    base_qty = _safe_float(latest.get("base_qty", latest.get("stock_qty", latest.get("qty", 0))))
    if base_qty <= 0:
        return 0.0

    try:
        base_unit = get_base_unit(items_df, item_id)
        if display_unit == base_unit:
            return round(base_qty, 1)

        qty = convert_unit(
            item_id=item_id,
            qty=base_qty,
            from_unit=base_unit,
            to_unit=display_unit,
            conversions_df=conversions_df,
            as_of_date=_parse_date(latest.get("stocktake_date")),
        )
        return round(qty, 1)
    except Exception:
        return round(base_qty, 1)

def _build_purchase_detail_df() -> pd.DataFrame:
    table_names = ("purchase_orders", "purchase_order_lines", "vendors", "items", "stores", "units")
    cache_key = "derived::purchase_detail_df"
    cached = _get_derived_cache(cache_key, table_names)
    if cached is not None:
        return cached

    po_df = read_table("purchase_orders")
    pol_df = read_table("purchase_order_lines")
    vendors_df = read_table("vendors")
    items_df = read_table("items")
    stores_df = read_table("stores")
    units_df = read_table("units")

    if po_df.empty or pol_df.empty:
        return _set_derived_cache(cache_key, table_names, pd.DataFrame())

    if "po_id" not in po_df.columns or "po_id" not in pol_df.columns:
        return _set_derived_cache(cache_key, table_names, pd.DataFrame())

    pol = pol_df.copy()
    if "base_unit" in pol.columns:
        pol = pol.drop(columns=["base_unit"])
    pol["po_id"] = _normalize_key_series(pol["po_id"])
    if "item_id" in pol.columns:
        pol["item_id"] = _normalize_key_series(pol["item_id"])
    else:
        pol["item_id"] = ""

    po_keep = pd.DataFrame({"po_id": _normalize_key_series(po_df["po_id"])})
    po_column_map = {
        "store_id": "po_store_id",
        "vendor_id": "po_vendor_id",
        "order_date": "po_order_date",
        "delivery_date": "po_delivery_date",
        "expected_date": "po_expected_date",
        "status": "po_status",
    }
    for src, dst in po_column_map.items():
        if src in po_df.columns:
            po_keep[dst] = po_df[src]

    merged = pol.merge(po_keep, on="po_id", how="left", copy=False)

    merged["store_id"] = _normalize_key_series(merged["po_store_id"] if "po_store_id" in merged.columns else "")
    merged["vendor_id"] = _normalize_key_series(merged["po_vendor_id"] if "po_vendor_id" in merged.columns else merged.get("vendor_id", ""))
    merged["item_id"] = _normalize_key_series(merged["item_id"])
    merged["order_date"] = (merged["po_order_date"] if "po_order_date" in merged.columns else merged.get("order_date", "")).astype(str)

    delivery_parts = []
    for col in ["delivery_date", "po_delivery_date", "po_expected_date"]:
        if col in merged.columns:
            delivery_parts.append(merged[col].astype("object"))
    if delivery_parts:
        delivery_series = delivery_parts[0]
        for part in delivery_parts[1:]:
            delivery_series = delivery_series.combine_first(part)
        merged["delivery_date"] = delivery_series.astype(str)
    else:
        merged["delivery_date"] = ""

    merged["status"] = (merged["po_status"] if "po_status" in merged.columns else merged.get("status", "")).astype(str)

    vendor_name_map = _build_preferred_label_map(vendors_df, "vendor_id", ["vendor_name_zh", "vendor_name", "vendor_id"], empty_default="")
    item_name_map = _build_preferred_label_map(items_df, "item_id", ["item_name_zh", "item_name", "item_id"], empty_default="")
    store_name_map = _build_preferred_label_map(stores_df, "store_id", ["store_name_zh", "store_name", "store_id"], empty_default="")
    unit_name_map = _build_preferred_label_map(units_df, "unit_id", ["unit_name_zh", "unit_name", "unit_id"], empty_default="")

    if not items_df.empty and "item_id" in items_df.columns:
        item_cols = ["item_id"] + [
            c for c in ["base_unit", "default_vendor_id", "default_stock_unit", "display_order"]
            if c in items_df.columns
        ]
        item_lookup = items_df.loc[:, item_cols].copy()
        item_lookup["item_id"] = _normalize_key_series(item_lookup["item_id"])
        merged = merged.merge(item_lookup, on="item_id", how="left", copy=False)

    merged["vendor_name_disp"] = merged["vendor_id"].map(vendor_name_map).fillna(merged["vendor_id"])
    merged["item_name_disp"] = merged["item_id"].map(item_name_map).fillna(merged["item_id"])
    merged["store_name_disp"] = merged["store_id"].map(store_name_map).fillna(merged["store_id"])

    merged["vendor_name_disp"] = merged["vendor_name_disp"].astype(str).str.strip()
    merged.loc[merged["vendor_name_disp"].str.lower().isin({"", "nan", "none", "nat", "-"}), "vendor_name_disp"] = ""

    merged["item_name_disp"] = merged["item_name_disp"].astype(str).str.strip()
    merged.loc[merged["item_name_disp"].str.lower().isin({"", "nan", "none", "nat"}), "item_name_disp"] = "未指定"

    merged["store_name_disp"] = merged["store_name_disp"].astype(str).str.strip()
    merged.loc[merged["store_name_disp"].str.lower().isin({"", "nan", "none", "nat"}), "store_name_disp"] = "未指定"

    merged["order_date_dt"] = pd.to_datetime(merged["order_date"], errors="coerce").dt.date
    merged["delivery_date_dt"] = pd.to_datetime(merged["delivery_date"], errors="coerce").dt.date
    merged["operation_date"] = merged["order_date"]
    merged["operation_date_dt"] = merged["order_date_dt"]

    qty_series = pd.to_numeric(merged["order_qty"], errors="coerce") if "order_qty" in merged.columns else pd.Series(0, index=merged.index, dtype="float64")
    if "qty" in merged.columns:
        qty_series = qty_series.fillna(pd.to_numeric(merged["qty"], errors="coerce"))
    merged["order_qty_num"] = qty_series.fillna(0.0)

    base_qty_series = pd.to_numeric(merged["base_qty"], errors="coerce") if "base_qty" in merged.columns else pd.Series(0, index=merged.index, dtype="float64")
    merged["order_base_qty_num"] = base_qty_series.fillna(0.0)

    merged["order_base_unit_disp"] = merged["base_unit"].astype(str).str.strip() if "base_unit" in merged.columns else ""

    unit_price_series = pd.to_numeric(merged["unit_price"], errors="coerce") if "unit_price" in merged.columns else pd.Series(0, index=merged.index, dtype="float64")
    merged["unit_price_num"] = unit_price_series.fillna(0.0)

    if "line_amount" in merged.columns:
        merged["amount_num"] = pd.to_numeric(merged["line_amount"], errors="coerce").fillna(0.0)
    elif "amount" in merged.columns:
        merged["amount_num"] = pd.to_numeric(merged["amount"], errors="coerce").fillna(0.0)
    else:
        merged["amount_num"] = merged["order_qty_num"] * merged["unit_price_num"]

    if "order_unit" in merged.columns:
        order_unit_series = merged["order_unit"].astype("object")
        if "unit_id" in merged.columns:
            order_unit_series = order_unit_series.combine_first(merged["unit_id"].astype("object"))
        merged["order_unit_disp"] = order_unit_series.astype(str).str.strip()
    elif "unit_id" in merged.columns:
        merged["order_unit_disp"] = merged["unit_id"].astype(str).str.strip()
    else:
        merged["order_unit_disp"] = ""
    merged["order_unit_disp"] = merged["order_unit_disp"].map(unit_name_map).fillna(merged["order_unit_disp"])

    if "display_order" in merged.columns:
        merged["display_order_num"] = pd.to_numeric(merged["display_order"], errors="coerce").fillna(999999)
    else:
        merged["display_order_num"] = 999999

    purchase_tail_order = [
        "order_date", "status", "vendor_name_disp", "item_name_disp", "store_name_disp",
        "base_unit", "default_vendor_id", "default_stock_unit",
        "order_date_dt", "delivery_date_dt", "operation_date", "operation_date_dt",
        "order_qty_num", "order_base_qty_num", "order_base_unit_disp",
        "unit_price_num", "amount_num", "order_unit_disp", "display_order_num",
    ]
    col_list = list(merged.columns)
    tail_positions = [idx for idx, col in enumerate(col_list) if col in purchase_tail_order]
    head_positions = [idx for idx, col in enumerate(col_list) if col not in purchase_tail_order]
    ordered_positions = head_positions + [col_list.index(col) for col in purchase_tail_order if col in col_list]
    merged = merged.iloc[:, ordered_positions]

    return _set_derived_cache(cache_key, table_names, merged)

def _build_stock_detail_df() -> pd.DataFrame:
    table_names = ("stocktakes", "stocktake_lines", "items", "vendors", "stores", "unit_conversions")
    cache_key = "derived::stock_detail_df"
    cached = _get_derived_cache(cache_key, table_names)
    if cached is not None:
        return cached

    st_df = read_table("stocktakes")
    stl_df = read_table("stocktake_lines")
    items_df = read_table("items")
    vendors_df = read_table("vendors")
    stores_df = read_table("stores")
    conversions_df = _get_active_df(read_table("unit_conversions"))

    if st_df.empty or stl_df.empty:
        return _set_derived_cache(cache_key, table_names, pd.DataFrame())

    if "stocktake_id" not in st_df.columns or "stocktake_id" not in stl_df.columns:
        return _set_derived_cache(cache_key, table_names, pd.DataFrame())

    stl = stl_df.copy()
    if "base_unit" in stl.columns:
        stl = stl.drop(columns=["base_unit"])
    stl["stocktake_id"] = _normalize_key_series(stl["stocktake_id"])
    if "item_id" in stl.columns:
        stl["item_id"] = _normalize_key_series(stl["item_id"])
    else:
        stl["item_id"] = ""

    st_keep = pd.DataFrame({"stocktake_id": _normalize_key_series(st_df["stocktake_id"])})
    st_column_map = {
        "store_id": "st_store_id",
        "stocktake_date": "st_stocktake_date",
        "note": "st_note",
        "created_at": "st_created_at",
        "updated_at": "st_updated_at",
    }
    for src, dst in st_column_map.items():
        if src in st_df.columns:
            st_keep[dst] = st_df[src]

    merged = stl.merge(st_keep, on="stocktake_id", how="left", copy=False)

    merged["store_id"] = _normalize_key_series(merged["st_store_id"] if "st_store_id" in merged.columns else merged.get("store_id", ""))
    merged["stocktake_date"] = (merged["st_stocktake_date"] if "st_stocktake_date" in merged.columns else merged.get("stocktake_date", "")).astype(str)

    note_series = (merged["st_note"] if "st_note" in merged.columns else merged.get("note", "")).astype(str)
    merged["note_for_parse"] = note_series
    vendor_series = merged["vendor_id"].astype(str).str.strip() if "vendor_id" in merged.columns else pd.Series("", index=merged.index, dtype="object")
    parsed_vendor = note_series.str.extract(r"vendor=([^\s]+)", expand=False).fillna("").astype(str).str.strip()
    merged["vendor_id"] = vendor_series.where(vendor_series != "", parsed_vendor)

    merged["stocktake_created_at"] = (merged["st_created_at"] if "st_created_at" in merged.columns else "").astype(str)
    merged["stocktake_updated_at"] = (merged["st_updated_at"] if "st_updated_at" in merged.columns else "").astype(str)

    merged["vendor_id"] = _normalize_key_series(merged["vendor_id"])
    merged["item_id"] = _normalize_key_series(merged["item_id"])

    if not items_df.empty and "item_id" in items_df.columns:
        item_cols = ["item_id"] + [
            c for c in ["base_unit", "default_vendor_id", "default_stock_unit", "display_order"]
            if c in items_df.columns
        ]
        item_lookup = items_df.loc[:, item_cols].copy()
        item_lookup["item_id"] = _normalize_key_series(item_lookup["item_id"])
        merged = merged.merge(item_lookup, on="item_id", how="left", copy=False)

        if "default_vendor_id" in merged.columns:
            default_vendor = merged["default_vendor_id"].astype(str).str.strip()
            merged["vendor_id"] = merged["vendor_id"].where(merged["vendor_id"] != "", default_vendor)
            merged["vendor_id"] = _normalize_key_series(merged["vendor_id"])

    item_name_map = _build_preferred_label_map(items_df, "item_id", ["item_name_zh", "item_name", "item_id"], empty_default="")
    vendor_name_map = _build_preferred_label_map(vendors_df, "vendor_id", ["vendor_name", "vendor_id"], empty_default="")
    store_name_map = _build_preferred_label_map(stores_df, "store_id", ["store_name_zh", "store_name", "store_id"], empty_default="")

    merged["item_name_disp"] = merged["item_id"].map(item_name_map).fillna(merged["item_id"])
    merged["vendor_name_disp"] = merged["vendor_id"].map(vendor_name_map).fillna(merged["vendor_id"])
    merged["store_name_disp"] = merged["store_id"].map(store_name_map).fillna(merged["store_id"])

    merged["vendor_name_disp"] = merged["vendor_name_disp"].astype(str).str.strip()
    merged.loc[merged["vendor_name_disp"].str.lower().isin({"", "nan", "none", "nat"}), "vendor_name_disp"] = "-"

    merged["item_name_disp"] = merged["item_name_disp"].astype(str).str.strip()
    merged.loc[merged["item_name_disp"].str.lower().isin({"", "nan", "none", "nat"}), "item_name_disp"] = "未指定"

    merged["store_name_disp"] = merged["store_name_disp"].astype(str).str.strip()
    merged.loc[merged["store_name_disp"].str.lower().isin({"", "nan", "none", "nat"}), "store_name_disp"] = "未指定"

    merged["stocktake_date_dt"] = pd.to_datetime(merged["stocktake_date"], errors="coerce").dt.date
    merged["operation_date"] = merged["stocktake_date"]
    merged["operation_date_dt"] = merged["stocktake_date_dt"]

    base_qty_series = pd.Series(0, index=merged.index, dtype="float64")
    for col in ["base_qty", "stock_qty", "qty"]:
        if col in merged.columns:
            base_qty_series = base_qty_series.where(base_qty_series != 0, pd.to_numeric(merged[col], errors="coerce").fillna(0.0))
    merged["base_qty_num"] = base_qty_series.fillna(0.0)

    if "default_stock_unit" in merged.columns:
        default_stock_unit = merged["default_stock_unit"].astype(str).str.strip()
        base_unit_series = merged["base_unit"].astype(str).str.strip() if "base_unit" in merged.columns else pd.Series("", index=merged.index, dtype="object")
        merged["display_stock_unit"] = default_stock_unit.where(default_stock_unit != "", base_unit_series)
    elif "base_unit" in merged.columns:
        merged["display_stock_unit"] = merged["base_unit"].astype(str).str.strip()
    else:
        merged["display_stock_unit"] = ""

    base_unit_series = merged["base_unit"].astype(str).str.strip() if "base_unit" in merged.columns else pd.Series("", index=merged.index, dtype="object")
    merged["display_stock_qty"] = _compute_display_qty_series(
        merged["item_id"],
        merged["base_qty_num"],
        base_unit_series,
        merged["display_stock_unit"],
        merged["stocktake_date_dt"],
        conversions_df,
        round_digits=1,
    )

    if "display_order" in merged.columns:
        merged["display_order_num"] = pd.to_numeric(merged["display_order"], errors="coerce").fillna(999999)
    else:
        merged["display_order_num"] = 999999

    return _set_derived_cache(cache_key, table_names, merged)

def _sum_purchase_qty_in_display_unit(
    item_po: pd.DataFrame,
    item_id: str,
    display_unit: str,
    conversions_df: pd.DataFrame,
    curr_date: date,
) -> float:
    total = 0.0
    if item_po.empty:
        return 0.0

    for _, po_row in item_po.iterrows():
        base_qty = _safe_float(po_row.get("order_base_qty_num", 0))
        base_unit = _norm(po_row.get("order_base_unit_disp", ""))

        if base_qty == 0:
            continue

        try:
            if base_unit and display_unit and base_unit != display_unit:
                qty_in_display = convert_unit(
                    item_id=item_id,
                    qty=base_qty,
                    from_unit=base_unit,
                    to_unit=display_unit,
                    conversions_df=conversions_df,
                    as_of_date=curr_date,
                )
            else:
                qty_in_display = base_qty
            total += float(qty_in_display)
        except Exception:
            total += float(base_qty)

    return round(total, 1)

def _build_inventory_history_summary_df(store_id: str, start_date: date, end_date: date) -> pd.DataFrame:
    store_id_norm = str(store_id).strip()
    signature = (
        store_id_norm,
        str(start_date),
        str(end_date),
        _table_versions_signature(("stocktakes", "stocktake_lines", "purchase_orders", "purchase_order_lines", "items", "vendors", "stores", "unit_conversions")),
    )
    cache_key = f"derived::inventory_history_summary::{store_id_norm}::{start_date}::{end_date}"
    cached = _session_df_cache_get(cache_key, signature)
    if cached is not None:
        return cached

    stock_df = _build_stock_detail_df()
    po_df = _build_purchase_detail_df()
    conversions_df = _get_active_df(read_table("unit_conversions"))

    if stock_df.empty or "store_id" not in stock_df.columns or "stocktake_date_dt" not in stock_df.columns:
        out = pd.DataFrame()
        _session_df_cache_set(cache_key, signature, out)
        return out

    stock_store_mask = stock_df["store_id"].astype(str).str.strip().eq(store_id_norm)
    stock_work = stock_df.loc[stock_store_mask].copy()
    stock_work = stock_work[stock_work["stocktake_date_dt"].notna()].copy()

    if stock_work.empty:
        out = pd.DataFrame()
        _session_df_cache_set(cache_key, signature, out)
        return out

    if "display_order_num" not in stock_work.columns:
        if "display_order" in stock_work.columns:
            stock_work["display_order_num"] = pd.to_numeric(stock_work["display_order"], errors="coerce").fillna(999999)
        else:
            stock_work["display_order_num"] = 999999

    target_stock = stock_work[
        stock_work["stocktake_date_dt"].between(start_date, end_date, inclusive="both")
    ].copy()

    if target_stock.empty:
        out = pd.DataFrame()
        _session_df_cache_set(cache_key, signature, out)
        return out

    if "stocktake_updated_at" not in target_stock.columns:
        target_stock["stocktake_updated_at"] = ""
    if "stocktake_created_at" not in target_stock.columns:
        target_stock["stocktake_created_at"] = ""

    target_stock["item_id"] = _normalize_key_series(target_stock["item_id"])
    target_stock["vendor_id"] = _normalize_key_series(target_stock["vendor_id"])
    target_stock["default_vendor_id"] = _normalize_key_series(target_stock.get("default_vendor_id", pd.Series("", index=target_stock.index, dtype="object")))
    target_stock["__effective_vendor_id"] = target_stock["vendor_id"].where(target_stock["vendor_id"] != "", target_stock["default_vendor_id"])
    target_stock["__sort_updated"] = pd.to_datetime(target_stock["stocktake_updated_at"], errors="coerce")
    target_stock["__sort_created"] = pd.to_datetime(target_stock["stocktake_created_at"], errors="coerce")

    target_stock = target_stock.sort_values(
        ["stocktake_date_dt", "vendor_id", "item_id", "__sort_updated", "__sort_created", "stocktake_id"],
        ascending=[True, True, True, True, True, True],
        kind="mergesort",
    ).drop_duplicates(
        subset=["stocktake_date_dt", "vendor_id", "item_id"],
        keep="last",
    ).copy()

    target_stock = target_stock.sort_values(
        ["item_id", "__effective_vendor_id", "stocktake_date_dt", "display_order_num", "item_name_disp"],
        ascending=[True, True, True, True, True],
        kind="mergesort",
    ).copy()

    group_cols = ["item_id", "__effective_vendor_id"]
    target_stock["prev_date"] = target_stock.groupby(group_cols, sort=False)["stocktake_date_dt"].shift(1)
    target_stock["prev_qty"] = pd.to_numeric(
        target_stock.groupby(group_cols, sort=False)["display_stock_qty"].shift(1),
        errors="coerce",
    ).fillna(0.0)
    target_stock["prev_base_qty"] = pd.to_numeric(
        target_stock.groupby(group_cols, sort=False)["base_qty_num"].shift(1),
        errors="coerce",
    ).fillna(0.0)

    po_work = pd.DataFrame()
    po_date_field = "operation_date_dt" if "operation_date_dt" in po_df.columns else "order_date_dt"
    if not po_df.empty and "store_id" in po_df.columns and po_date_field in po_df.columns:
        po_store_mask = po_df["store_id"].astype(str).str.strip().eq(store_id_norm)
        po_work = po_df.loc[po_store_mask].copy()
        po_work = po_work[po_work[po_date_field].notna()].copy()

    if not po_work.empty:
        po_work["item_id"] = _normalize_key_series(po_work["item_id"])
        po_work["vendor_id"] = _normalize_key_series(po_work["vendor_id"])

        latest_item_vendor = target_stock.drop_duplicates(subset=["item_id", "__effective_vendor_id"], keep="last")
        latest_item = target_stock.drop_duplicates(subset=["item_id"], keep="last")

        display_unit_map = latest_item_vendor.set_index(["item_id", "__effective_vendor_id"])["display_stock_unit"].to_dict()
        fallback_display_unit_map = latest_item.set_index("item_id")["display_stock_unit"].to_dict()
        fallback_base_unit_map = latest_item.set_index("item_id")["base_unit"].to_dict()

        po_display_unit = pd.Series(list(zip(po_work["item_id"], po_work["vendor_id"])), index=po_work.index).map(display_unit_map)
        po_display_unit = po_display_unit.fillna(po_work["item_id"].map(fallback_display_unit_map))
        po_display_unit = po_display_unit.fillna(po_work["item_id"].map(fallback_base_unit_map)).fillna("")
        po_work["display_stock_unit"] = po_display_unit.astype(str).str.strip()

        po_work["order_display_qty_num"] = _compute_display_qty_series(
            item_ids=po_work["item_id"],
            base_qtys=po_work["order_base_qty_num"],
            base_units=po_work["order_base_unit_disp"],
            display_units=po_work["display_stock_unit"],
            as_of_dates=po_work[po_date_field],
            conversions_df=conversions_df,
            round_digits=1,
        )

        po_daily = (
            po_work.groupby(["item_id", "vendor_id", po_date_field], as_index=False)
            .agg(
                order_display_qty_num=("order_display_qty_num", "sum"),
                order_base_qty_num=("order_base_qty_num", "sum"),
            )
            .sort_values(["item_id", "vendor_id", po_date_field], ascending=[True, True, True], kind="mergesort")
            .reset_index(drop=True)
        )
        po_daily["cum_display_qty"] = po_daily.groupby(["item_id", "vendor_id"], sort=False)["order_display_qty_num"].cumsum()
        po_daily["cum_base_qty"] = po_daily.groupby(["item_id", "vendor_id"], sort=False)["order_base_qty_num"].cumsum()

        same_day = po_daily.rename(columns={
            po_date_field: "stocktake_date_dt",
            "order_display_qty_num": "這次叫貨",
            "order_base_qty_num": "這次叫貨_base_qty",
        })[["item_id", "vendor_id", "stocktake_date_dt", "這次叫貨", "這次叫貨_base_qty"]]

        target_stock = target_stock.merge(
            same_day,
            left_on=["item_id", "__effective_vendor_id", "stocktake_date_dt"],
            right_on=["item_id", "vendor_id", "stocktake_date_dt"],
            how="left",
            sort=False,
        )
        if "vendor_id_y" in target_stock.columns:
            target_stock = target_stock.drop(columns=["vendor_id_y"])
        if "vendor_id_x" in target_stock.columns:
            target_stock = target_stock.rename(columns={"vendor_id_x": "vendor_id"})

        target_stock["這次叫貨"] = pd.to_numeric(target_stock["這次叫貨"], errors="coerce").fillna(0.0).round(1)
        target_stock["這次叫貨_base_qty"] = pd.to_numeric(target_stock["這次叫貨_base_qty"], errors="coerce").fillna(0.0).round(4)

        po_lookup: dict[tuple[str, str], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for key, grp in po_daily.groupby(["item_id", "vendor_id"], sort=False):
            po_lookup[key] = (
                grp[po_date_field].to_numpy(dtype="datetime64[ns]"),
                grp["cum_display_qty"].to_numpy(dtype="float64"),
                grp["cum_base_qty"].to_numpy(dtype="float64"),
            )

        target_stock["期間進貨"] = 0.0
        target_stock["期間進貨_base_qty"] = 0.0
        for key, row_index in target_stock.groupby(group_cols, sort=False).groups.items():
            dates_arr, cum_display_arr, cum_base_arr = po_lookup.get(
                key,
                (np.array([], dtype="datetime64[ns]"), np.array([], dtype="float64"), np.array([], dtype="float64")),
            )
            if dates_arr.size == 0:
                target_stock.loc[row_index, "期間進貨"] = target_stock.loc[row_index, "這次叫貨"].to_numpy(dtype="float64")
                target_stock.loc[row_index, "期間進貨_base_qty"] = target_stock.loc[row_index, "這次叫貨_base_qty"].to_numpy(dtype="float64")
                continue

            curr_dates = pd.to_datetime(target_stock.loc[row_index, "stocktake_date_dt"], errors="coerce").to_numpy(dtype="datetime64[ns]")
            prev_dates = pd.to_datetime(target_stock.loc[row_index, "prev_date"], errors="coerce").to_numpy(dtype="datetime64[ns]")
            curr_pos = np.searchsorted(dates_arr, curr_dates, side="right") - 1
            prev_pos = np.searchsorted(dates_arr, prev_dates, side="right") - 1

            curr_cum_display = np.where(curr_pos >= 0, cum_display_arr[np.clip(curr_pos, 0, None)], 0.0)
            curr_cum_base = np.where(curr_pos >= 0, cum_base_arr[np.clip(curr_pos, 0, None)], 0.0)
            prev_cum_display = np.where(prev_pos >= 0, cum_display_arr[np.clip(prev_pos, 0, None)], 0.0)
            prev_cum_base = np.where(prev_pos >= 0, cum_base_arr[np.clip(prev_pos, 0, None)], 0.0)

            period_display = np.round(curr_cum_display - prev_cum_display, 1)
            period_base = np.round(curr_cum_base - prev_cum_base, 4)
            first_mask = pd.isna(target_stock.loc[row_index, "prev_date"]).to_numpy()
            if first_mask.any():
                same_day_display_vals = target_stock.loc[row_index, "這次叫貨"].to_numpy(dtype="float64")
                same_day_base_vals = target_stock.loc[row_index, "這次叫貨_base_qty"].to_numpy(dtype="float64")
                period_display = np.where(first_mask, same_day_display_vals, period_display)
                period_base = np.where(first_mask, same_day_base_vals, period_base)

            target_stock.loc[row_index, "期間進貨"] = period_display
            target_stock.loc[row_index, "期間進貨_base_qty"] = period_base
    else:
        target_stock["這次叫貨"] = 0.0
        target_stock["這次叫貨_base_qty"] = 0.0
        target_stock["期間進貨"] = 0.0
        target_stock["期間進貨_base_qty"] = 0.0

    target_stock["上次庫存"] = pd.to_numeric(target_stock["prev_qty"], errors="coerce").fillna(0.0).round(1)
    target_stock["上次庫存_base_qty"] = pd.to_numeric(target_stock["prev_base_qty"], errors="coerce").fillna(0.0).round(4)
    target_stock["這次庫存"] = pd.to_numeric(target_stock["display_stock_qty"], errors="coerce").fillna(0.0).round(1)
    target_stock["這次庫存_base_qty"] = pd.to_numeric(target_stock["base_qty_num"], errors="coerce").fillna(0.0).round(4)
    target_stock["庫存合計"] = (target_stock["上次庫存"] + target_stock["期間進貨"]).round(1)
    target_stock["庫存合計_base_qty"] = (target_stock["上次庫存_base_qty"] + target_stock["期間進貨_base_qty"]).round(4)

    prev_date_series = pd.to_datetime(target_stock["prev_date"], errors="coerce")
    curr_date_series = pd.to_datetime(target_stock["stocktake_date_dt"], errors="coerce")
    has_prev_mask = prev_date_series.notna()

    target_stock["期間消耗"] = 0.0
    target_stock["期間消耗_base_qty"] = 0.0
    target_stock.loc[has_prev_mask, "期間消耗"] = (
        target_stock.loc[has_prev_mask, "庫存合計"] - target_stock.loc[has_prev_mask, "這次庫存"]
    ).round(1)
    target_stock.loc[has_prev_mask, "期間消耗_base_qty"] = (
        target_stock.loc[has_prev_mask, "庫存合計_base_qty"] - target_stock.loc[has_prev_mask, "這次庫存_base_qty"]
    ).round(4)

    target_stock["天數"] = 0
    if has_prev_mask.any():
        delta_days = (curr_date_series[has_prev_mask] - prev_date_series[has_prev_mask]).dt.days.clip(lower=1)
        target_stock.loc[has_prev_mask, "天數"] = delta_days.astype(int)

    target_stock["日平均"] = 0.0
    nonzero_days_mask = target_stock["天數"].gt(0)
    if nonzero_days_mask.any():
        usage_vals = target_stock.loc[nonzero_days_mask, "期間消耗"].tolist()
        day_vals = target_stock.loc[nonzero_days_mask, "天數"].tolist()
        target_stock.loc[nonzero_days_mask, "日平均"] = [
            round(float(usage) / int(days), 1) if int(days) > 0 else 0.0
            for usage, days in zip(usage_vals, day_vals)
        ]

    out = target_stock[[
        "stocktake_date_dt",
        "vendor_name_disp",
        "__effective_vendor_id",
        "item_name_disp",
        "上次庫存",
        "上次庫存_base_qty",
        "期間進貨",
        "期間進貨_base_qty",
        "庫存合計",
        "庫存合計_base_qty",
        "這次庫存",
        "這次庫存_base_qty",
        "期間消耗",
        "期間消耗_base_qty",
        "這次叫貨",
        "這次叫貨_base_qty",
        "日平均",
        "天數",
        "item_id",
        "display_order_num",
    ]].rename(columns={
        "stocktake_date_dt": "日期",
        "vendor_name_disp": "廠商",
        "__effective_vendor_id": "vendor_id",
        "item_name_disp": "品項",
    }).copy()

    out["廠商"] = out["廠商"].astype(str).str.strip()
    out["vendor_id"] = out["vendor_id"].astype(str).str.strip()
    out["品項"] = out["品項"].astype(str).str.strip()
    out["display_order_num"] = pd.to_numeric(out["display_order_num"], errors="coerce").fillna(999999.0).astype(float)
    out.loc[out["廠商"].eq(""), "廠商"] = out.loc[out["廠商"].eq(""), "vendor_id"]
    out.loc[out["廠商"].eq(""), "廠商"] = "-"
    out.loc[out["品項"].eq(""), "品項"] = "未指定"

    if out.empty:
        _session_df_cache_set(cache_key, signature, out)
        return out

    out["日期_dt"] = pd.to_datetime(out["日期"], errors="coerce")
    out["日期顯示"] = out["日期_dt"].dt.strftime("%m-%d")
    out = out.sort_values(["日期_dt", "display_order_num", "品項"], ascending=[False, True, True], kind="mergesort").reset_index(drop=True)
    _session_df_cache_set(cache_key, signature, out)
    return out

def _build_latest_item_metrics_df(store_id: str, as_of_date: date) -> pd.DataFrame:
    signature = (
        str(store_id).strip(),
        str(as_of_date),
        _table_versions_signature(("stocktakes", "stocktake_lines", "purchase_orders", "purchase_order_lines", "items", "vendors", "stores", "unit_conversions")),
    )
    cache_key = f"derived::latest_item_metrics::{str(store_id).strip()}::{as_of_date}"
    cached = _session_df_cache_get(cache_key, signature)
    if cached is not None:
        return cached

    stock_df = _build_stock_detail_df()
    if stock_df.empty or "store_id" not in stock_df.columns or "stocktake_date_dt" not in stock_df.columns:
        out = pd.DataFrame()
        _session_df_cache_set(cache_key, signature, out)
        return out

    stock_work = stock_df[
        stock_df["store_id"].astype(str).str.strip() == str(store_id).strip()
    ].copy()
    stock_work = stock_work[stock_work["stocktake_date_dt"].notna()].copy()
    stock_work = stock_work[stock_work["stocktake_date_dt"] <= as_of_date].copy()

    if stock_work.empty:
        out = pd.DataFrame()
        _session_df_cache_set(cache_key, signature, out)
        return out

    if "display_order_num" not in stock_work.columns:
        if "display_order" in stock_work.columns:
            stock_work["display_order_num"] = pd.to_numeric(stock_work["display_order"], errors="coerce").fillna(999999)
        else:
            stock_work["display_order_num"] = 999999

    if "stocktake_updated_at" not in stock_work.columns:
        stock_work["stocktake_updated_at"] = ""
    if "stocktake_created_at" not in stock_work.columns:
        stock_work["stocktake_created_at"] = ""

    stock_work["item_id"] = _normalize_key_series(stock_work.get("item_id", pd.Series(dtype="object")))
    stock_work["vendor_id"] = _normalize_key_series(stock_work.get("vendor_id", pd.Series(dtype="object")))
    stock_work["item_name_disp"] = stock_work.get("item_name_disp", pd.Series("", index=stock_work.index)).astype(str)
    stock_work["vendor_name_disp"] = stock_work.get("vendor_name_disp", pd.Series("", index=stock_work.index)).astype(str)
    stock_work["base_qty_num"] = pd.to_numeric(stock_work.get("base_qty_num", 0), errors="coerce").fillna(0.0)
    stock_work["display_stock_qty"] = pd.to_numeric(stock_work.get("display_stock_qty", 0), errors="coerce").fillna(0.0)
    stock_work["__sort_updated"] = pd.to_datetime(stock_work["stocktake_updated_at"], errors="coerce")
    stock_work["__sort_created"] = pd.to_datetime(stock_work["stocktake_created_at"], errors="coerce")

    stock_work = stock_work.sort_values(
        ["stocktake_date_dt", "vendor_id", "item_id", "__sort_updated", "__sort_created", "stocktake_id"],
        ascending=[True, True, True, True, True, True],
    ).drop_duplicates(
        subset=["stocktake_date_dt", "vendor_id", "item_id"],
        keep="last",
    ).copy()

    stock_work["stocktake_date_dt"] = pd.to_datetime(stock_work["stocktake_date_dt"], errors="coerce")
    stock_work = stock_work.sort_values(
        ["item_id", "vendor_id", "stocktake_date_dt", "display_order_num", "item_name_disp"],
        ascending=[True, True, True, True, True],
    ).reset_index(drop=True)

    group_cols = ["item_id", "vendor_id"]
    stock_work["prev_date"] = stock_work.groupby(group_cols)["stocktake_date_dt"].shift(1)
    stock_work["prev_qty"] = stock_work.groupby(group_cols)["display_stock_qty"].shift(1).fillna(0.0)
    stock_work["prev_base_qty"] = stock_work.groupby(group_cols)["base_qty_num"].shift(1).fillna(0.0)

    latest = stock_work.groupby(group_cols, as_index=False).tail(1).copy()
    if latest.empty:
        out = pd.DataFrame()
        _session_df_cache_set(cache_key, signature, out)
        return out

    latest["prev_date"] = pd.to_datetime(latest["prev_date"], errors="coerce")
    latest["item_name"] = latest["item_name_disp"].map(_norm).replace("", "未指定")
    latest["vendor_name"] = latest["vendor_name_disp"].map(_norm)
    latest.loc[latest["vendor_name"] == "", "vendor_name"] = latest["vendor_id"].where(latest["vendor_id"] != "", "-")
    latest["curr_qty"] = latest["display_stock_qty"].astype(float)
    latest["curr_base_qty"] = latest["base_qty_num"].astype(float)

    latest["window_start"] = latest["prev_date"].where(latest["prev_date"].notna(), latest["stocktake_date_dt"])
    latest["window_end"] = latest["stocktake_date_dt"]

    summary_window_start = latest["window_start"].min()
    if pd.isna(summary_window_start):
        summary_window_start = latest["stocktake_date_dt"].min()
    summary_window_start = pd.to_datetime(summary_window_start, errors="coerce")

    summary_signature = (
        str(store_id).strip(),
        str(summary_window_start.date()) if pd.notna(summary_window_start) else str(as_of_date),
        str(as_of_date),
        _table_versions_signature(("stocktakes", "stocktake_lines", "purchase_orders", "purchase_order_lines", "items", "vendors", "stores", "unit_conversions")),
    )
    summary_cache_key = f"derived::inventory_history_summary::{str(store_id).strip()}::{summary_window_start.date() if pd.notna(summary_window_start) else as_of_date}::{as_of_date}"
    summary_cached = _session_df_cache_get(summary_cache_key, summary_signature)
    if summary_cached is not None and not summary_cached.empty:
        summary_latest = summary_cached.copy()
        summary_latest["日期_dt"] = pd.to_datetime(summary_latest.get("日期_dt", summary_latest.get("日期")), errors="coerce")
        summary_latest = summary_latest[summary_latest["日期_dt"].notna()].copy()
        summary_latest = summary_latest.sort_values(["item_id", "vendor_id", "日期_dt"], ascending=[True, True, True])
        summary_latest = summary_latest.groupby(["item_id", "vendor_id"], as_index=False).tail(1).copy()
        summary_latest = summary_latest.sort_values(["display_order_num", "品項"], ascending=[True, True]).reset_index(drop=True)
        _session_df_cache_set(cache_key, signature, summary_latest)
        return summary_latest

    po_df = _build_purchase_detail_df()
    po_date_field = "operation_date_dt" if "operation_date_dt" in po_df.columns else "order_date_dt"
    po_daily = pd.DataFrame()

    if not po_df.empty and "store_id" in po_df.columns and po_date_field in po_df.columns:
        po_work = po_df[
            po_df["store_id"].astype(str).str.strip() == str(store_id).strip()
        ].copy()
        po_work = po_work[po_work[po_date_field].notna()].copy()
        po_work[po_date_field] = pd.to_datetime(po_work[po_date_field], errors="coerce")
        if pd.notna(summary_window_start):
            po_work = po_work[po_work[po_date_field] >= summary_window_start].copy()
        po_work = po_work[po_work[po_date_field] <= pd.Timestamp(as_of_date)].copy()

        if not po_work.empty:
            po_work = po_work.loc[:, [
                col for col in ["item_id", "vendor_id", po_date_field, "order_base_qty_num", "order_base_unit_disp"]
                if col in po_work.columns
            ]].copy()
            po_work["item_id"] = _normalize_key_series(po_work.get("item_id", pd.Series(dtype="object")))
            po_work["vendor_id"] = _normalize_key_series(po_work.get("vendor_id", pd.Series(dtype="object")))
            po_work["order_base_qty_num"] = pd.to_numeric(po_work.get("order_base_qty_num", 0), errors="coerce").fillna(0.0)
            po_work["order_base_unit_disp"] = po_work.get("order_base_unit_disp", pd.Series("", index=po_work.index)).astype(str)

            latest_windows = latest[["item_id", "vendor_id", "window_start", "window_end"]].drop_duplicates(subset=["item_id", "vendor_id"], keep="last")
            po_work = po_work.merge(latest_windows, on=["item_id", "vendor_id"], how="inner", copy=False)
            po_work = po_work[
                (po_work[po_date_field] >= po_work["window_start"])
                & (po_work[po_date_field] <= po_work["window_end"])
            ].copy()

            if not po_work.empty:
                conversions_df = _get_active_df(read_table("unit_conversions"))

                latest_unit_by_pair = latest.set_index(["item_id", "vendor_id"])["display_stock_unit"].astype(str).to_dict()
                latest_unit_by_item = latest.drop_duplicates(subset=["item_id"], keep="last").set_index("item_id")["display_stock_unit"].astype(str).to_dict()
                latest_base_unit_by_item = latest.drop_duplicates(subset=["item_id"], keep="last").set_index("item_id")["base_unit"].astype(str).to_dict()

                po_work["display_unit"] = [
                    _norm(latest_unit_by_pair.get((item_id, vendor_id), ""))
                    or _norm(latest_unit_by_item.get(item_id, ""))
                    or _norm(latest_base_unit_by_item.get(item_id, ""))
                    for item_id, vendor_id in zip(po_work["item_id"], po_work["vendor_id"])
                ]

                factor_keys = (
                    po_work[["item_id", "order_base_unit_disp", "display_unit", po_date_field]]
                    .drop_duplicates()
                    .reset_index(drop=True)
                )
                factor_cache: dict = {}
                factor_map: dict[tuple[str, str, str, pd.Timestamp], float] = {}
                for item_id, base_unit, display_unit, curr_date in factor_keys.itertuples(index=False, name=None):
                    item_key = _norm(item_id)
                    base_unit_key = _norm(base_unit)
                    display_unit_key = _norm(display_unit)
                    date_key = pd.Timestamp(curr_date)
                    key = (item_key, base_unit_key, display_unit_key, date_key)
                    factor_map[key] = 1.0
                    if base_unit_key and display_unit_key and base_unit_key != display_unit_key:
                        qty = _convert_base_qty_with_cache(
                            item_id=item_key,
                            base_qty=1.0,
                            base_unit=base_unit_key,
                            display_unit=display_unit_key,
                            conversions_df=conversions_df,
                            as_of_date=date_key,
                            factor_cache=factor_cache,
                        )
                        factor_map[key] = float(qty)

                po_keys = list(zip(po_work["item_id"], po_work["order_base_unit_disp"], po_work["display_unit"], po_work[po_date_field]))
                po_factors = [factor_map.get((_norm(item_id), _norm(base_unit), _norm(display_unit), pd.Timestamp(curr_date)), 1.0) for item_id, base_unit, display_unit, curr_date in po_keys]
                po_work["order_display_qty_num"] = (po_work["order_base_qty_num"].astype(float) * pd.Series(po_factors, index=po_work.index)).round(1)

                po_daily = (
                    po_work.groupby(["item_id", "vendor_id", po_date_field], as_index=False)
                    .agg(
                        order_display_qty_num=("order_display_qty_num", "sum"),
                        order_base_qty_num=("order_base_qty_num", "sum"),
                    )
                    .sort_values(["item_id", "vendor_id", po_date_field], ascending=[True, True, True])
                    .reset_index(drop=True)
                )
                po_daily["cum_display_qty"] = po_daily.groupby(["item_id", "vendor_id"])["order_display_qty_num"].cumsum()
                po_daily["cum_base_qty"] = po_daily.groupby(["item_id", "vendor_id"])["order_base_qty_num"].cumsum()

    latest = latest.sort_values(["item_id", "vendor_id", "stocktake_date_dt"], ascending=[True, True, True]).reset_index(drop=True)
    latest["current_order_qty"] = 0.0
    latest["current_order_base_qty"] = 0.0
    latest["curr_cum_display"] = 0.0
    latest["curr_cum_base"] = 0.0
    latest["prev_cum_display"] = 0.0
    latest["prev_cum_base"] = 0.0

    if not po_daily.empty:
        po_daily = po_daily.sort_values(["item_id", "vendor_id", po_date_field], ascending=[True, True, True]).reset_index(drop=True)
        po_daily_idx = po_daily.set_index(["item_id", "vendor_id", po_date_field])
        same_day_display = po_daily_idx["order_display_qty_num"].to_dict()
        same_day_base = po_daily_idx["order_base_qty_num"].to_dict()
        cum_by_group = {
            key: grp[[po_date_field, "cum_display_qty", "cum_base_qty"]].sort_values(po_date_field).reset_index(drop=True)
            for key, grp in po_daily.groupby(["item_id", "vendor_id"], sort=False)
        }

        latest["current_order_qty"] = [
            round(_safe_float(same_day_display.get((item_id, vendor_id, curr_date), 0.0)), 1)
            for item_id, vendor_id, curr_date in zip(latest["item_id"], latest["vendor_id"], latest["stocktake_date_dt"])
        ]
        latest["current_order_base_qty"] = [
            round(_safe_float(same_day_base.get((item_id, vendor_id, curr_date), 0.0)), 4)
            for item_id, vendor_id, curr_date in zip(latest["item_id"], latest["vendor_id"], latest["stocktake_date_dt"])
        ]

        curr_cum_display_vals = []
        curr_cum_base_vals = []
        prev_cum_display_vals = []
        prev_cum_base_vals = []
        for item_id, vendor_id, curr_date, prev_date in zip(latest["item_id"], latest["vendor_id"], latest["stocktake_date_dt"], latest["prev_date"]):
            grp = cum_by_group.get((item_id, vendor_id))
            curr_display = 0.0
            curr_base = 0.0
            prev_display = 0.0
            prev_base = 0.0
            if grp is not None and not grp.empty:
                dates = grp[po_date_field]
                curr_pos = dates.searchsorted(curr_date, side="right") - 1
                prev_pos = dates.searchsorted(prev_date, side="right") - 1 if pd.notna(prev_date) else -1
                if curr_pos >= 0:
                    curr_display = float(grp.iloc[curr_pos]["cum_display_qty"])
                    curr_base = float(grp.iloc[curr_pos]["cum_base_qty"])
                if prev_pos >= 0:
                    prev_display = float(grp.iloc[prev_pos]["cum_display_qty"])
                    prev_base = float(grp.iloc[prev_pos]["cum_base_qty"])
            curr_cum_display_vals.append(curr_display)
            curr_cum_base_vals.append(curr_base)
            prev_cum_display_vals.append(prev_display)
            prev_cum_base_vals.append(prev_base)

        latest["curr_cum_display"] = curr_cum_display_vals
        latest["curr_cum_base"] = curr_cum_base_vals
        latest["prev_cum_display"] = prev_cum_display_vals
        latest["prev_cum_base"] = prev_cum_base_vals

    has_prev = latest["prev_date"].notna()
    latest["order_sum"] = latest["current_order_qty"]
    latest["order_sum_base_qty"] = latest["current_order_base_qty"]
    latest.loc[has_prev, "order_sum"] = (latest.loc[has_prev, "curr_cum_display"] - latest.loc[has_prev, "prev_cum_display"]).round(1)
    latest.loc[has_prev, "order_sum_base_qty"] = (latest.loc[has_prev, "curr_cum_base"] - latest.loc[has_prev, "prev_cum_base"]).round(4)

    latest["total_stock"] = (latest["prev_qty"] + latest["order_sum"]).round(1)
    latest["total_stock_base_qty"] = (latest["prev_base_qty"] + latest["order_sum_base_qty"]).round(4)
    latest["usage"] = 0.0
    latest["usage_base_qty"] = 0.0
    latest.loc[has_prev, "usage"] = (latest.loc[has_prev, "total_stock"] - latest.loc[has_prev, "curr_qty"]).round(1)
    latest.loc[has_prev, "usage_base_qty"] = (latest.loc[has_prev, "total_stock_base_qty"] - latest.loc[has_prev, "curr_base_qty"]).round(4)
    latest["days"] = 0
    latest.loc[has_prev, "days"] = (latest.loc[has_prev, "stocktake_date_dt"] - latest.loc[has_prev, "prev_date"]).dt.days.clip(lower=1).astype(int)
    latest["daily_avg"] = [
        round((_safe_float(usage) / int(days)), 1) if int(days) > 0 else 0.0
        for usage, days in zip(latest["usage"], latest["days"])
    ]

    out = pd.DataFrame(
        {
            "日期": latest["stocktake_date_dt"].dt.date,
            "廠商": latest["vendor_name"],
            "vendor_id": latest["vendor_id"],
            "品項": latest["item_name"],
            "上次庫存": latest["prev_qty"].round(1),
            "上次庫存_base_qty": latest["prev_base_qty"].round(4),
            "期間進貨": latest["order_sum"].round(1),
            "期間進貨_base_qty": latest["order_sum_base_qty"].round(4),
            "庫存合計": latest["total_stock"].round(1),
            "庫存合計_base_qty": latest["total_stock_base_qty"].round(4),
            "這次庫存": latest["curr_qty"].round(1),
            "這次庫存_base_qty": latest["curr_base_qty"].round(4),
            "期間消耗": latest["usage"].round(1),
            "期間消耗_base_qty": latest["usage_base_qty"].round(4),
            "這次叫貨": latest["current_order_qty"].round(1),
            "這次叫貨_base_qty": latest["current_order_base_qty"].round(4),
            "日平均": latest["daily_avg"].round(1),
            "天數": latest["days"].astype(int),
            "item_id": latest["item_id"],
            "display_order_num": pd.to_numeric(latest["display_order_num"], errors="coerce").fillna(999999),
        }
    )

    out["日期_dt"] = pd.to_datetime(out["日期"], errors="coerce")
    out["日期顯示"] = out["日期_dt"].dt.strftime("%m-%d")
    out = out.sort_values(["display_order_num", "品項"], ascending=[True, True]).reset_index(drop=True)
    _session_df_cache_set(cache_key, signature, out)
    return out

def _build_purchase_summary_df(store_id: str, start_date: date, end_date: date) -> pd.DataFrame:
    po_df = _build_purchase_detail_df()
    date_field = "operation_date_dt" if "operation_date_dt" in po_df.columns else "order_date_dt"
    if po_df.empty or "store_id" not in po_df.columns or date_field not in po_df.columns:
        return pd.DataFrame()

    po_work = po_df[
        po_df["store_id"].astype(str).str.strip() == str(store_id).strip()
    ].copy()

    po_work = po_work[
        po_work[date_field].notna()
        & (po_work[date_field] >= start_date)
        & (po_work[date_field] <= end_date)
    ].copy()

    if po_work.empty:
        return pd.DataFrame()

    po_work["廠商"] = po_work["vendor_name_disp"].apply(
        lambda x: "" if _norm(x).lower() in {"", "nan", "none", "nat", "-"} else _norm(x)
    )
    po_work["品項名稱"] = po_work["item_name_disp"].apply(
        lambda x: _norm(x) or "未指定"
    )
    po_work["單位"] = po_work["order_unit_disp"].apply(lambda x: _norm(x))
    po_work["單價"] = po_work["unit_price_num"].astype(float)
    po_work["叫貨數量"] = po_work["order_qty_num"].astype(float)
    po_work["採購金額"] = po_work["amount_num"].astype(float)

    out = (
        po_work.groupby(["廠商", "品項名稱", "單位", "單價"], as_index=False)
        .agg(
            叫貨數量=("叫貨數量", "sum"),
            採購金額=("採購金額", "sum"),
        )
        .sort_values(["廠商", "品項名稱"], ascending=[True, True])
        .reset_index(drop=True)
    )
    return out
