from __future__ import annotations

from datetime import date

import pandas as pd

from shared.utils.common_helpers import _norm
from shared.utils.utils_format import unit_label
from data_management.services.service_purchase import (
    PurchaseServiceError,
    create_item,
    create_price,
    create_unit,
    create_unit_conversion,
    create_vendor,
    get_brand_options,
    list_active_items,
    list_active_units,
    list_active_vendors,
    list_items,
    list_prices,
    list_unit_conversions,
    list_units,
    list_vendors,
    update_item,
    update_price,
    update_unit,
    update_unit_conversion,
    update_vendor,
)


__all__ = [
    "PurchaseServiceError",
    "build_vendor_context",
    "build_unit_context",
    "build_item_context",
    "build_price_context",
    "build_unit_conversion_context",
    "get_vendor_edit_values",
    "get_unit_edit_values",
    "get_item_edit_values",
    "get_price_edit_values",
    "get_conversion_edit_values",
    "submit_create_vendor",
    "submit_update_vendor",
    "submit_create_unit",
    "submit_update_unit",
    "submit_create_item",
    "submit_update_item",
    "submit_create_price",
    "submit_update_price",
    "submit_create_unit_conversion",
    "submit_update_unit_conversion",
]


def bool_text(v) -> str:
    text = str(v).strip().lower()
    return "啟用" if text in {"true", "1", "yes", "y"} else "停用"


def vendor_label_from_row(r: pd.Series) -> str:
    return _norm(r.get("vendor_name_zh")) or _norm(r.get("vendor_name"))


def unit_label_from_row(r: pd.Series) -> str:
    return _norm(r.get("unit_name_zh")) or _norm(r.get("unit_name"))


def item_label_from_row(r: pd.Series) -> str:
    return _norm(r.get("item_name_zh")) or _norm(r.get("item_name"))


def fmt_price_1(v) -> str:
    try:
        return f"{float(v):.1f}"
    except Exception:
        return str(v)


def normalize_brand_options() -> tuple[list[str], dict[str, str]]:
    brand_map = {label: brand_id for label, brand_id in get_brand_options()}
    return list(brand_map.keys()), brand_map


def filter_items_by_vendor(items_df: pd.DataFrame, vendor_id: str) -> pd.DataFrame:
    if items_df.empty:
        return items_df.copy()
    if not _norm(vendor_id):
        return items_df.copy()
    if "default_vendor_id" not in items_df.columns:
        return items_df.copy()
    return items_df[items_df["default_vendor_id"].astype(str) == _norm(vendor_id)].copy()


def build_vendor_options(vendors_df: pd.DataFrame) -> dict[str, str]:
    if vendors_df.empty:
        return {}
    return {vendor_label_from_row(r): _norm(r.get("vendor_id")) for _, r in vendors_df.iterrows()}


def build_unit_options(units_df: pd.DataFrame) -> dict[str, str]:
    if units_df.empty:
        return {}
    return {
        unit_label_from_row(r): _norm(r.get("unit_name_zh") or r.get("unit_name") or r.get("unit_id"))
        for _, r in units_df.iterrows()
    }


def build_unit_id_options(units_df: pd.DataFrame) -> dict[str, str]:
    if units_df.empty:
        return {}
    return {unit_label_from_row(r): _norm(r.get("unit_id")) for _, r in units_df.iterrows()}


def build_item_options(items_df: pd.DataFrame) -> dict[str, str]:
    if items_df.empty:
        return {}
    return {item_label_from_row(r): _norm(r.get("item_id")) for _, r in items_df.iterrows()}


def filter_active_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "is_active" not in df.columns:
        return df.copy()
    return df[df["is_active"].astype(str).str.lower().isin(["true", "1", "yes", "y"])].copy()


def build_vendor_display_df(vendors_df: pd.DataFrame, show_inactive: bool) -> pd.DataFrame:
    view_df = vendors_df.copy()
    if not show_inactive:
        view_df = filter_active_rows(view_df)
    if view_df.empty:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            "廠商名稱": view_df["vendor_name_zh"].replace("", pd.NA).fillna(view_df["vendor_name"]),
            "聯絡人": view_df.get("contact_name", ""),
            "電話": view_df.get("phone", ""),
            "LINE": view_df.get("line_id", ""),
            "狀態": view_df.get("is_active", "").apply(bool_text),
        }
    )


def build_unit_display_df(units_df: pd.DataFrame, show_inactive: bool) -> pd.DataFrame:
    view_df = units_df.copy()
    if not show_inactive:
        view_df = filter_active_rows(view_df)
    if view_df.empty:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            "單位名稱": view_df["unit_name_zh"].replace("", pd.NA).fillna(view_df["unit_name"]),
            "符號": view_df.get("unit_symbol", ""),
            "類型": view_df.get("unit_type", ""),
            "狀態": view_df.get("is_active", "").apply(bool_text),
        }
    )


def build_item_display_df(items_df: pd.DataFrame, search_text: str, show_inactive: bool) -> pd.DataFrame:
    view_df = items_df.copy()
    keyword = _norm(search_text).lower()
    if keyword:
        name_zh = view_df.get("item_name_zh", pd.Series(dtype=str)).astype(str).str.lower()
        name_en = view_df.get("item_name", pd.Series(dtype=str)).astype(str).str.lower()
        view_df = view_df[name_zh.str.contains(keyword, na=False) | name_en.str.contains(keyword, na=False)]
    if not show_inactive:
        view_df = filter_active_rows(view_df)
    if view_df.empty:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            "品項名稱": view_df["item_name_zh"].replace("", pd.NA).fillna(view_df["item_name"]),
            "分類": view_df.get("category", ""),
            "基準單位": view_df.get("base_unit", "").apply(unit_label),
            "庫存單位": view_df.get("default_stock_unit", "").apply(unit_label),
            "叫貨單位": view_df.get("default_order_unit", "").apply(unit_label),
            "可叫貨單位": view_df.get("orderable_units", "").apply(
                lambda x: "、".join(unit_label(v.strip()) for v in str(x or "").split(",") if v.strip())
            ),
            "狀態": view_df.get("is_active", "").apply(bool_text),
        }
    )


def build_price_display_df(prices_df: pd.DataFrame) -> pd.DataFrame:
    if prices_df.empty:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            "生效日期": prices_df.get("effective_date", ""),
            "單價": prices_df.get("unit_price", ""),
            "單位": prices_df.get("price_unit", "").apply(unit_label),
            "結束日期": prices_df.get("end_date", ""),
            "狀態": prices_df.get("is_active", "").apply(bool_text),
        }
    )


def build_conversion_display_df(conv_df: pd.DataFrame) -> pd.DataFrame:
    if conv_df.empty:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            "換算": conv_df.apply(
                lambda r: f"1{unit_label(r.get('from_unit'))} = {_norm(r.get('ratio'))}{unit_label(r.get('to_unit'))}",
                axis=1,
            ),
            "狀態": conv_df.get("is_active", "").apply(bool_text),
        }
    )


def build_price_option_map(prices_df: pd.DataFrame) -> dict[str, str]:
    if prices_df.empty:
        return {}
    return {
        f"{_norm(r.get('effective_date'))}｜{fmt_price_1(r.get('unit_price'))}/{unit_label(r.get('price_unit'))}": _norm(r.get("price_id"))
        for _, r in prices_df.iterrows()
    }


def build_conversion_option_map(conv_df: pd.DataFrame) -> dict[str, str]:
    if conv_df.empty:
        return {}
    return {
        f"1{unit_label(r.get('from_unit'))} = {_norm(r.get('ratio'))}{unit_label(r.get('to_unit'))}｜{_norm(r.get('conversion_id'))}": _norm(r.get("conversion_id"))
        for _, r in conv_df.iterrows()
    }


def find_option_index(option_map: dict[str, str], target: str, default: int = 0) -> int:
    keys = list(option_map.keys())
    for i, label in enumerate(keys):
        if option_map.get(label) == _norm(target):
            return i
    return default


def find_unit_label_index(unit_options: dict[str, str], target: str) -> int:
    keys = list(unit_options.keys())
    for i, label in enumerate(keys):
        if unit_options.get(label) == _norm(target):
            return i
    return 0


def get_row_by_id(df: pd.DataFrame, id_column: str, value: str) -> pd.Series:
    if df.empty or id_column not in df.columns:
        raise PurchaseServiceError("查無資料")
    matched = df[df[id_column].astype(str) == _norm(value)]
    if matched.empty:
        raise PurchaseServiceError("查無資料")
    return matched.iloc[0]


def build_vendor_context(show_inactive: bool = False) -> dict:
    vendors_df = list_vendors()
    brand_labels, brand_map = normalize_brand_options()
    return {
        "vendors_df": vendors_df,
        "brand_keys": brand_labels,
        "brand_map": brand_map,
        "vendor_options": build_vendor_options(vendors_df),
        "display_df": build_vendor_display_df(vendors_df, show_inactive=show_inactive),
    }


def build_unit_context(show_inactive: bool = False) -> dict:
    units_df = list_units()
    brand_labels, brand_map = normalize_brand_options()
    return {
        "units_df": units_df,
        "brand_keys": brand_labels,
        "brand_map": brand_map,
        "unit_options": build_unit_id_options(units_df),
        "display_df": build_unit_display_df(units_df, show_inactive=show_inactive),
    }


def build_item_context(vendor_id: str, search_text: str = "", show_inactive: bool = False) -> dict:
    items_df = list_items()
    vendors_df = list_active_vendors()
    units_df = list_active_units()
    brand_labels, brand_map = normalize_brand_options()
    filtered_items_df = filter_items_by_vendor(items_df, vendor_id)
    return {
        "vendors_df": vendors_df,
        "units_df": units_df,
        "brand_keys": brand_labels,
        "brand_map": brand_map,
        "vendor_options": build_vendor_options(vendors_df),
        "unit_options": build_unit_id_options(units_df),
        "filtered_items_df": filtered_items_df,
        "item_options": build_item_options(filtered_items_df),
        "display_df": build_item_display_df(filtered_items_df, search_text=search_text, show_inactive=show_inactive),
    }


def build_price_context(vendor_id: str) -> dict:
    vendors_df = list_active_vendors()
    items_df = list_active_items()
    units_df = list_active_units()
    filtered_items_df = filter_items_by_vendor(items_df, vendor_id)
    return {
        "vendors_df": vendors_df,
        "filtered_items_df": filtered_items_df,
        "vendor_options": build_vendor_options(vendors_df),
        "unit_options": build_unit_id_options(units_df),
        "item_options": build_item_options(filtered_items_df),
    }


def build_price_item_context(item_id: str) -> dict:
    prices_df = list_prices(item_id=item_id)
    return {
        "prices_df": prices_df,
        "price_options": build_price_option_map(prices_df),
        "display_df": build_price_display_df(prices_df),
    }


def build_unit_conversion_context(vendor_id: str) -> dict:
    vendors_df = list_active_vendors()
    items_df = list_active_items()
    units_df = list_active_units()
    filtered_items_df = filter_items_by_vendor(items_df, vendor_id)
    return {
        "vendors_df": vendors_df,
        "filtered_items_df": filtered_items_df,
        "vendor_options": build_vendor_options(vendors_df),
        "unit_options": build_unit_id_options(units_df),
        "item_options": build_item_options(filtered_items_df),
    }


def build_conversion_item_context(item_id: str) -> dict:
    conv_df = list_unit_conversions(item_id=item_id)
    return {
        "conv_df": conv_df,
        "conversion_options": build_conversion_option_map(conv_df),
        "display_df": build_conversion_display_df(conv_df),
    }


def get_vendor_edit_values(vendors_df: pd.DataFrame, vendor_id: str, brand_map: dict[str, str]) -> dict:
    row = get_row_by_id(vendors_df, "vendor_id", vendor_id)
    brand_idx = find_option_index({k: v for k, v in brand_map.items()}, _norm(row.get("brand_id"))) if brand_map else 0
    return {
        "row": row,
        "vendor_name_zh": _norm(row.get("vendor_name_zh")),
        "vendor_name": _norm(row.get("vendor_name")),
        "contact_name": _norm(row.get("contact_name")),
        "phone": _norm(row.get("phone")),
        "line_id": _norm(row.get("line_id")),
        "notes": _norm(row.get("notes")),
        "is_active": bool_text(row.get("is_active")) == "啟用",
        "brand_idx": brand_idx,
    }


def get_unit_edit_values(units_df: pd.DataFrame, unit_id: str, brand_map: dict[str, str]) -> dict:
    row = get_row_by_id(units_df, "unit_id", unit_id)
    brand_idx = find_option_index({k: v for k, v in brand_map.items()}, _norm(row.get("brand_id"))) if brand_map else 0
    return {
        "row": row,
        "unit_name_zh": _norm(row.get("unit_name_zh")),
        "unit_name": _norm(row.get("unit_name")),
        "unit_symbol": _norm(row.get("unit_symbol")),
        "unit_type": _norm(row.get("unit_type")),
        "is_active": bool_text(row.get("is_active")) == "啟用",
        "brand_idx": brand_idx,
    }


def get_item_edit_values(filtered_items_df: pd.DataFrame, item_id: str, brand_map: dict[str, str], unit_options: dict[str, str]) -> dict:
    row = get_row_by_id(filtered_items_df, "item_id", item_id)
    current_orderable = [x.strip() for x in _norm(row.get("orderable_units")).split(",") if x.strip()]
    default_orderable = [label for label, value in unit_options.items() if value in current_orderable]
    brand_idx = find_option_index({k: v for k, v in brand_map.items()}, _norm(row.get("brand_id"))) if brand_map else 0
    return {
        "row": row,
        "item_name_zh": _norm(row.get("item_name_zh")),
        "item_name": _norm(row.get("item_name")),
        "category": _norm(row.get("category")),
        "spec": _norm(row.get("note")) or _norm(row.get("spec_value")) or _norm(row.get("spec")),
        "is_active": bool_text(row.get("is_active")) == "啟用",
        "brand_idx": brand_idx,
        "base_unit_idx": find_unit_label_index(unit_options, _norm(row.get("base_unit"))),
        "stock_unit_idx": find_unit_label_index(unit_options, _norm(row.get("default_stock_unit"))),
        "order_unit_idx": find_unit_label_index(unit_options, _norm(row.get("default_order_unit"))),
        "default_orderable": default_orderable,
    }


def get_price_edit_values(prices_df: pd.DataFrame, price_id: str, unit_options: dict[str, str]) -> dict:
    row = get_row_by_id(prices_df, "price_id", price_id)
    effective_date_text = _norm(row.get("effective_date"))
    try:
        effective_date_value = pd.to_datetime(effective_date_text).date()
    except Exception:
        effective_date_value = date.today()
    return {
        "row": row,
        "unit_price": float(_norm(row.get("unit_price")) or 0),
        "price_unit_idx": find_unit_label_index(unit_options, _norm(row.get("price_unit"))),
        "effective_date": effective_date_value,
        "end_date": _norm(row.get("end_date")),
        "is_active": bool_text(row.get("is_active")) == "啟用",
    }


def get_conversion_edit_values(conv_df: pd.DataFrame, conversion_id: str, unit_options: dict[str, str]) -> dict:
    row = get_row_by_id(conv_df, "conversion_id", conversion_id)
    ratio_raw = _norm(row.get("ratio"))
    try:
        ratio_value = int(round(float(ratio_raw or 0)))
    except Exception:
        ratio_value = 0
    return {
        "row": row,
        "from_unit_idx": find_unit_label_index(unit_options, _norm(row.get("from_unit"))),
        "to_unit_idx": find_unit_label_index(unit_options, _norm(row.get("to_unit"))),
        "ratio": ratio_value,
        "is_active": bool_text(row.get("is_active")) == "啟用",
    }


def validate_vendor_payload(payload: dict):
    if not _norm(payload.get("vendor_name_zh")):
        raise PurchaseServiceError("廠商名稱不可空白")


def validate_unit_payload(payload: dict):
    if not _norm(payload.get("unit_name_zh")):
        raise PurchaseServiceError("單位名稱不可空白")


def validate_item_payload(payload: dict):
    if not _norm(payload.get("item_name_zh")):
        raise PurchaseServiceError("品項名稱不可空白")
    if not _norm(payload.get("default_vendor_id")):
        raise PurchaseServiceError("請先選擇供應商")
    if not _norm(payload.get("base_unit")):
        raise PurchaseServiceError("請選擇基準單位")
    if not _norm(payload.get("default_stock_unit")):
        raise PurchaseServiceError("請選擇庫存單位")
    if not _norm(payload.get("default_order_unit")):
        raise PurchaseServiceError("請選擇預設叫貨單位")
    if not payload.get("orderable_units"):
        raise PurchaseServiceError("請至少選擇一個可叫貨單位")


def validate_price_payload(payload: dict):
    if not _norm(payload.get("item_id")):
        raise PurchaseServiceError("請先選擇品項")
    if not _norm(payload.get("price_unit")):
        raise PurchaseServiceError("請選擇價格單位")
    try:
        if float(payload.get("unit_price", 0) or 0) < 0:
            raise PurchaseServiceError("單價不可為負數")
    except (TypeError, ValueError):
        pass


def validate_conversion_payload(payload: dict):
    if not _norm(payload.get("item_id")):
        raise PurchaseServiceError("請先選擇品項")
    if not _norm(payload.get("from_unit")):
        raise PurchaseServiceError("請選擇來源單位")
    if not _norm(payload.get("to_unit")):
        raise PurchaseServiceError("請選擇目標單位")
    if _norm(payload.get("from_unit")) == _norm(payload.get("to_unit")):
        raise PurchaseServiceError("來源單位與目標單位不可相同")


def submit_create_vendor(**payload):
    validate_vendor_payload(payload)
    return create_vendor(**payload)


def submit_update_vendor(**payload):
    validate_vendor_payload(payload)
    return update_vendor(**payload)


def submit_create_unit(**payload):
    validate_unit_payload(payload)
    return create_unit(**payload)


def submit_update_unit(**payload):
    validate_unit_payload(payload)
    return update_unit(**payload)


def submit_create_item(**payload):
    validate_item_payload(payload)
    return create_item(**payload)


def submit_update_item(**payload):
    validate_item_payload(payload)
    return update_item(**payload)


def submit_create_price(**payload):
    validate_price_payload(payload)
    return create_price(**payload)


def submit_update_price(**payload):
    validate_price_payload(payload)
    return update_price(**payload)


def submit_create_unit_conversion(**payload):
    validate_conversion_payload(payload)
    return create_unit_conversion(**payload)


def submit_update_unit_conversion(**payload):
    validate_conversion_payload(payload)
    return update_unit_conversion(**payload)
