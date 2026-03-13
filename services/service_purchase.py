"""
服務層：採購設定 / 資料管理服務。

目前版本採 item-only 模型：
- 一個 item = 一個實際採購規格
- prices / unit_conversions 都先綁 item_id
- spec 相關欄位先保留但不使用
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from oms_core import (
    _norm,
    _now_ts,
    _safe_float,
    allocate_ids,
    append_rows_by_header,
    bust_cache,
    get_header,
    get_spreadsheet,
    read_table,
)


# ============================================================
# [S1] 基本例外 / 共用
# ============================================================
class PurchaseServiceError(Exception):
    """資料管理頁用的可顯示錯誤。"""


def _to_bool_text(v: bool) -> str:
    return "TRUE" if bool(v) else "FALSE"


def _today_str(v: date | str | None = None) -> str:
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    text = _norm(v)
    return text or date.today().strftime("%Y-%m-%d")


def _df_sorted(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    valid_cols = [c for c in columns if c in df.columns]
    if not valid_cols:
        return df.copy()
    return df.sort_values(valid_cols, ascending=True).reset_index(drop=True)


def _ensure_not_empty(value: str, label: str):
    if not _norm(value):
        raise PurchaseServiceError(f"{label}不可空白")


def _normalize_multi_units(units: list[str]) -> str:
    cleaned = []
    for x in units:
        t = _norm(x)
        if t:
            cleaned.append(t)
    cleaned = list(dict.fromkeys(cleaned))
    return ",".join(cleaned)


def _find_sheet_row_number(sheet_name: str, id_field: str, entity_id: str) -> int:
    sh = get_spreadsheet()
    if sh is None:
        raise PurchaseServiceError("Spreadsheet 未初始化")

    ws = sh.worksheet(sheet_name)
    values = ws.get_all_values()
    if not values:
        raise PurchaseServiceError(f"{sheet_name} 工作表為空")

    header = [_norm(x) for x in values[0]]
    if id_field not in header:
        raise PurchaseServiceError(f"{sheet_name} 缺少欄位：{id_field}")

    id_idx = header.index(id_field)
    for i, row in enumerate(values[1:], start=2):
        cell = row[id_idx] if id_idx < len(row) else ""
        if _norm(cell) == _norm(entity_id):
            return i

    raise PurchaseServiceError(f"{sheet_name} 找不到 {entity_id}")


def _update_row_by_id(sheet_name: str, id_field: str, entity_id: str, updates: dict[str, Any]):
    sh = get_spreadsheet()
    if sh is None:
        raise PurchaseServiceError("Spreadsheet 未初始化")

    ws = sh.worksheet(sheet_name)
    header = [_norm(x) for x in ws.row_values(1)]
    row_num = _find_sheet_row_number(sheet_name, id_field, entity_id)

    row_values = ws.row_values(row_num)
    if len(row_values) < len(header):
        row_values = row_values + [""] * (len(header) - len(row_values))
    else:
        row_values = row_values[:len(header)]

    current = {col: row_values[idx] for idx, col in enumerate(header)}

    for key, value in updates.items():
        if key in current:
            current[key] = "" if value is None else str(value)

    new_row = [current.get(col, "") for col in header]
    start_col_letter = "A"
    end_col_letter = _col_to_letter(len(header))
    ws.update(f"{start_col_letter}{row_num}:{end_col_letter}{row_num}", [new_row], value_input_option="USER_ENTERED")
    bust_cache()


def _col_to_letter(n: int) -> str:
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def _brand_id_or_default(brand_id: str) -> str:
    text = _norm(brand_id)
    if text:
        return text

    brands_df = read_table("brands")
    if brands_df.empty or "brand_id" not in brands_df.columns:
        return ""

    active_df = brands_df.copy()
    if "is_active" in active_df.columns:
        active_df = active_df[
            active_df["is_active"].astype(str).str.lower().isin(["true", "1", "yes", "y"])
        ]

    if active_df.empty:
        return _norm(brands_df.iloc[0].get("brand_id"))
    return _norm(active_df.iloc[0].get("brand_id"))


def get_brand_options() -> list[tuple[str, str]]:
    brands_df = read_table("brands")
    if brands_df.empty:
        return [("預設品牌", "")]

    work = brands_df.copy()
    if "is_active" in work.columns:
        work = work[work["is_active"].astype(str).str.lower().isin(["true", "1", "yes", "y"])]

    out: list[tuple[str, str]] = []
    for _, r in work.iterrows():
        brand_id = _norm(r.get("brand_id"))
        brand_name = _norm(r.get("brand_name_zh")) or _norm(r.get("brand_name")) or brand_id
        out.append((brand_name, brand_id))

    return out or [("預設品牌", "")]


# ============================================================
# [S2] 讀取清單
# ============================================================
def list_vendors() -> pd.DataFrame:
    df = read_table("vendors").copy()
    if df.empty:
        return df
    sort_cols = []
    if "vendor_name_zh" in df.columns:
        sort_cols.append("vendor_name_zh")
    elif "vendor_name" in df.columns:
        sort_cols.append("vendor_name")
    return _df_sorted(df, sort_cols or ["vendor_id"])


def list_active_vendors() -> pd.DataFrame:
    df = list_vendors()
    if df.empty:
        return df
    if "is_active" in df.columns:
        df = df[df["is_active"].astype(str).str.lower().isin(["true", "1", "yes", "y"])]
    return df.reset_index(drop=True)


def list_units() -> pd.DataFrame:
    df = read_table("units").copy()
    if df.empty:
        return df
    sort_cols = []
    if "unit_name_zh" in df.columns:
        sort_cols.append("unit_name_zh")
    elif "unit_name" in df.columns:
        sort_cols.append("unit_name")
    return _df_sorted(df, sort_cols or ["unit_id"])


def list_active_units() -> pd.DataFrame:
    df = list_units()
    if df.empty:
        return df
    if "is_active" in df.columns:
        df = df[df["is_active"].astype(str).str.lower().isin(["true", "1", "yes", "y"])]
    return df.reset_index(drop=True)


def list_items() -> pd.DataFrame:
    df = read_table("items").copy()
    if df.empty:
        return df
    sort_cols = []
    if "item_name_zh" in df.columns:
        sort_cols.append("item_name_zh")
    elif "item_name" in df.columns:
        sort_cols.append("item_name")
    return _df_sorted(df, sort_cols or ["item_id"])


def list_active_items() -> pd.DataFrame:
    df = list_items()
    if df.empty:
        return df
    if "is_active" in df.columns:
        df = df[df["is_active"].astype(str).str.lower().isin(["true", "1", "yes", "y"])]
    return df.reset_index(drop=True)


def list_prices(item_id: str = "") -> pd.DataFrame:
    df = read_table("prices").copy()
    if df.empty:
        return df

    if _norm(item_id) and "item_id" in df.columns:
        df = df[df["item_id"].astype(str) == _norm(item_id)]

    sort_cols = []
    if "effective_date" in df.columns:
        sort_cols.append("effective_date")
    df = _df_sorted(df, sort_cols or ["price_id"])

    if "effective_date" in df.columns:
        df = df.sort_values("effective_date", ascending=False).reset_index(drop=True)
    return df


def list_unit_conversions(item_id: str = "") -> pd.DataFrame:
    df = read_table("unit_conversions").copy()
    if df.empty:
        return df

    if _norm(item_id) and "item_id" in df.columns:
        df = df[df["item_id"].astype(str) == _norm(item_id)]

    sort_cols = []
    if "from_unit" in df.columns:
        sort_cols.append("from_unit")
    if "to_unit" in df.columns:
        sort_cols.append("to_unit")
    return _df_sorted(df, sort_cols or ["conversion_id"])


# ============================================================
# [S3] 建立資料
# ============================================================
def create_vendor(
    *,
    vendor_name_zh: str,
    vendor_name: str = "",
    contact_name: str = "",
    phone: str = "",
    line_id: str = "",
    notes: str = "",
    is_active: bool = True,
    brand_id: str = "",
) -> str:
    _ensure_not_empty(vendor_name_zh, "廠商名稱")

    df = list_vendors()
    dup = df[
        df["vendor_name_zh"].astype(str).str.strip().str.lower() == _norm(vendor_name_zh).lower()
    ] if not df.empty and "vendor_name_zh" in df.columns else pd.DataFrame()

    if not dup.empty:
        raise PurchaseServiceError("廠商名稱重複，請確認後再新增")

    new_id = allocate_ids({"vendors": 1})["vendors"][0]
    now = _now_ts()
    brand_id = _brand_id_or_default(brand_id)

    row = {
        "vendor_id": new_id,
        "brand_id": brand_id,
        "vendor_code": new_id,
        "vendor_name": _norm(vendor_name) or _norm(vendor_name_zh),
        "vendor_name_zh": _norm(vendor_name_zh),
        "contact_name": _norm(contact_name),
        "phone": _norm(phone),
        "line_id": _norm(line_id),
        "notes": _norm(notes),
        "is_active": _to_bool_text(is_active),
        "created_at": now,
        "updated_at": now,
    }

    header = get_header("vendors")
    append_rows_by_header("vendors", header, [row])
    bust_cache()
    return new_id


def create_unit(
    *,
    unit_name_zh: str,
    unit_name: str = "",
    unit_symbol: str = "",
    unit_type: str = "",
    is_active: bool = True,
    brand_id: str = "",
) -> str:
    _ensure_not_empty(unit_name_zh, "單位名稱")

    df = list_units()
    dup = df[
        df["unit_name_zh"].astype(str).str.strip().str.lower() == _norm(unit_name_zh).lower()
    ] if not df.empty and "unit_name_zh" in df.columns else pd.DataFrame()

    if not dup.empty:
        raise PurchaseServiceError("單位名稱重複，請確認後再新增")

    new_id = allocate_ids({"units": 1})["units"][0]
    now = _now_ts()
    brand_id = _brand_id_or_default(brand_id)

    row = {
        "unit_id": new_id,
        "brand_id": brand_id,
        "unit_name": _norm(unit_name) or _norm(unit_name_zh),
        "unit_name_zh": _norm(unit_name_zh),
        "unit_type": _norm(unit_type),
        "unit_symbol": _norm(unit_symbol),
        "is_active": _to_bool_text(is_active),
        "created_at": now,
        "updated_at": now,
    }

    header = get_header("units")
    append_rows_by_header("units", header, [row])
    bust_cache()
    return new_id


def create_item(
    *,
    item_name_zh: str,
    item_name: str = "",
    category: str = "",
    spec: str = "",
    default_vendor_id: str = "",
    base_unit: str = "",
    default_stock_unit: str = "",
    default_order_unit: str = "",
    orderable_units: list[str] | None = None,
    is_active: bool = True,
    brand_id: str = "",
) -> str:
    _ensure_not_empty(item_name_zh, "品項名稱")
    _ensure_not_empty(default_vendor_id, "預設供應商")
    _ensure_not_empty(base_unit, "基準單位")
    _ensure_not_empty(default_stock_unit, "庫存單位")
    _ensure_not_empty(default_order_unit, "預設叫貨單位")

    orderable_units = orderable_units or []
    orderable_units_text = _normalize_multi_units(orderable_units)
    if not orderable_units_text:
        raise PurchaseServiceError("可叫貨單位不可空白")

    if _norm(default_order_unit) not in [x.strip() for x in orderable_units_text.split(",") if x.strip()]:
        raise PurchaseServiceError("預設叫貨單位必須包含在可叫貨單位中")

    df = list_items()
    dup = df[
        df["item_name_zh"].astype(str).str.strip().str.lower() == _norm(item_name_zh).lower()
    ] if not df.empty and "item_name_zh" in df.columns else pd.DataFrame()

    if not dup.empty:
        raise PurchaseServiceError("品項名稱重複，請確認後再新增")

    new_id = allocate_ids({"items": 1})["items"][0]
    now = _now_ts()
    brand_id = _brand_id_or_default(brand_id)

    row = {
        "item_id": new_id,
        "brand_id": brand_id,
        "default_vendor_id": _norm(default_vendor_id),
        "item_name": _norm(item_name) or _norm(item_name_zh),
        "item_name_zh": _norm(item_name_zh),
        "item_type": "ingredient",
        "base_unit": _norm(base_unit),
        "default_stock_unit": _norm(default_stock_unit),
        "default_order_unit": _norm(default_order_unit),
        "orderable_units": orderable_units_text,
        "is_active": _to_bool_text(is_active),
        "category": _norm(category),
        "spec": _norm(spec),
        "created_at": now,
        "updated_at": now,
    }

    header = get_header("items")
    append_rows_by_header("items", header, [row])
    bust_cache()
    return new_id


def create_price(
    *,
    item_id: str,
    unit_price: float,
    price_unit: str,
    effective_date: date | str,
    is_active: bool = True,
) -> str:
    _ensure_not_empty(item_id, "品項")
    _ensure_not_empty(price_unit, "價格單位")

    price_val = _safe_float(unit_price, 0.0)
    if price_val <= 0:
        raise PurchaseServiceError("單價必須大於 0")

    new_id = allocate_ids({"prices": 1})["prices"][0]
    now = _now_ts()

    row = {
        "price_id": new_id,
        "item_id": _norm(item_id),
        "unit_price": str(price_val),
        "price_unit": _norm(price_unit),
        "effective_date": _today_str(effective_date),
        "end_date": "",
        "is_active": _to_bool_text(is_active),
        "created_at": now,
        "updated_at": now,
    }

    header = get_header("prices")
    append_rows_by_header("prices", header, [row])
    bust_cache()
    return new_id


def create_unit_conversion(
    *,
    item_id: str,
    from_unit: str,
    to_unit: str,
    ratio: float,
    is_active: bool = True,
) -> str:
    _ensure_not_empty(item_id, "品項")
    _ensure_not_empty(from_unit, "來源單位")
    _ensure_not_empty(to_unit, "目標單位")

    if _norm(from_unit) == _norm(to_unit):
        raise PurchaseServiceError("來源單位與目標單位不可相同")

    ratio_val = _safe_float(ratio, 0.0)
    if ratio_val <= 0:
        raise PurchaseServiceError("比例必須大於 0")

    df = list_unit_conversions(item_id=item_id)
    dup = df[
        (df["from_unit"].astype(str).str.strip() == _norm(from_unit))
        & (df["to_unit"].astype(str).str.strip() == _norm(to_unit))
    ] if not df.empty else pd.DataFrame()

    if not dup.empty:
        raise PurchaseServiceError("相同的單位換算已存在")

    new_id = allocate_ids({"unit_conversions": 1})["unit_conversions"][0]
    now = _now_ts()

    row = {
        "conversion_id": new_id,
        "item_id": _norm(item_id),
        "from_unit": _norm(from_unit),
        "to_unit": _norm(to_unit),
        "ratio": str(ratio_val),
        "is_active": _to_bool_text(is_active),
        "created_at": now,
        "updated_at": now,
    }

    header = get_header("unit_conversions")
    append_rows_by_header("unit_conversions", header, [row])
    bust_cache()
    return new_id


# ============================================================
# [S4] 更新資料
# ============================================================
def update_vendor(
    *,
    vendor_id: str,
    vendor_name_zh: str,
    vendor_name: str = "",
    contact_name: str = "",
    phone: str = "",
    line_id: str = "",
    notes: str = "",
    is_active: bool = True,
    brand_id: str = "",
):
    _ensure_not_empty(vendor_id, "廠商ID")
    _ensure_not_empty(vendor_name_zh, "廠商名稱")

    now = _now_ts()
    updates = {
        "brand_id": _brand_id_or_default(brand_id),
        "vendor_name": _norm(vendor_name) or _norm(vendor_name_zh),
        "vendor_name_zh": _norm(vendor_name_zh),
        "contact_name": _norm(contact_name),
        "phone": _norm(phone),
        "line_id": _norm(line_id),
        "notes": _norm(notes),
        "is_active": _to_bool_text(is_active),
        "updated_at": now,
    }
    _update_row_by_id("vendors", "vendor_id", vendor_id, updates)


def update_unit(
    *,
    unit_id: str,
    unit_name_zh: str,
    unit_name: str = "",
    unit_symbol: str = "",
    unit_type: str = "",
    is_active: bool = True,
    brand_id: str = "",
):
    _ensure_not_empty(unit_id, "單位ID")
    _ensure_not_empty(unit_name_zh, "單位名稱")

    now = _now_ts()
    updates = {
        "brand_id": _brand_id_or_default(brand_id),
        "unit_name": _norm(unit_name) or _norm(unit_name_zh),
        "unit_name_zh": _norm(unit_name_zh),
        "unit_symbol": _norm(unit_symbol),
        "unit_type": _norm(unit_type),
        "is_active": _to_bool_text(is_active),
        "updated_at": now,
    }
    _update_row_by_id("units", "unit_id", unit_id, updates)


def update_item(
    *,
    item_id: str,
    item_name_zh: str,
    item_name: str = "",
    category: str = "",
    spec: str = "",
    default_vendor_id: str = "",
    base_unit: str = "",
    default_stock_unit: str = "",
    default_order_unit: str = "",
    orderable_units: list[str] | None = None,
    is_active: bool = True,
    brand_id: str = "",
):
    _ensure_not_empty(item_id, "品項ID")
    _ensure_not_empty(item_name_zh, "品項名稱")
    _ensure_not_empty(default_vendor_id, "預設供應商")
    _ensure_not_empty(base_unit, "基準單位")
    _ensure_not_empty(default_stock_unit, "庫存單位")
    _ensure_not_empty(default_order_unit, "預設叫貨單位")

    orderable_units = orderable_units or []
    orderable_units_text = _normalize_multi_units(orderable_units)
    if not orderable_units_text:
        raise PurchaseServiceError("可叫貨單位不可空白")

    if _norm(default_order_unit) not in [x.strip() for x in orderable_units_text.split(",") if x.strip()]:
        raise PurchaseServiceError("預設叫貨單位必須包含在可叫貨單位中")

    now = _now_ts()
    updates = {
        "brand_id": _brand_id_or_default(brand_id),
        "default_vendor_id": _norm(default_vendor_id),
        "item_name": _norm(item_name) or _norm(item_name_zh),
        "item_name_zh": _norm(item_name_zh),
        "item_type": "ingredient",
        "base_unit": _norm(base_unit),
        "default_stock_unit": _norm(default_stock_unit),
        "default_order_unit": _norm(default_order_unit),
        "orderable_units": orderable_units_text,
        "is_active": _to_bool_text(is_active),
        "category": _norm(category),
        "spec": _norm(spec),
        "updated_at": now,
    }
    _update_row_by_id("items", "item_id", item_id, updates)


def update_price(
    *,
    price_id: str,
    unit_price: float,
    price_unit: str,
    effective_date: date | str,
    end_date: str = "",
    is_active: bool = True,
):
    _ensure_not_empty(price_id, "價格ID")
    _ensure_not_empty(price_unit, "價格單位")

    price_val = _safe_float(unit_price, 0.0)
    if price_val <= 0:
        raise PurchaseServiceError("單價必須大於 0")

    now = _now_ts()
    updates = {
        "unit_price": str(price_val),
        "price_unit": _norm(price_unit),
        "effective_date": _today_str(effective_date),
        "end_date": _norm(end_date),
        "is_active": _to_bool_text(is_active),
        "updated_at": now,
    }
    _update_row_by_id("prices", "price_id", price_id, updates)


def update_unit_conversion(
    *,
    conversion_id: str,
    from_unit: str,
    to_unit: str,
    ratio: float,
    is_active: bool = True,
):
    _ensure_not_empty(conversion_id, "換算ID")
    _ensure_not_empty(from_unit, "來源單位")
    _ensure_not_empty(to_unit, "目標單位")

    if _norm(from_unit) == _norm(to_unit):
        raise PurchaseServiceError("來源單位與目標單位不可相同")

    ratio_val = _safe_float(ratio, 0.0)
    if ratio_val <= 0:
        raise PurchaseServiceError("比例必須大於 0")

    now = _now_ts()
    updates = {
        "from_unit": _norm(from_unit),
        "to_unit": _norm(to_unit),
        "ratio": str(ratio_val),
        "is_active": _to_bool_text(is_active),
        "updated_at": now,
    }
    _update_row_by_id("unit_conversions", "conversion_id", conversion_id, updates)
