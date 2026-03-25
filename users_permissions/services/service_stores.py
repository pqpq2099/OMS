from __future__ import annotations

from datetime import datetime

import pandas as pd

from shared.services.service_audit import audit_log
from shared.services.service_id import allocate_store_id
from shared.services.service_sheet import (
    sheet_append,
    sheet_bust_cache,
    sheet_get_header,
    sheet_read_many,
    sheet_replace_table,
    sheet_update,
)


class StoreServiceError(ValueError):
    """分店管理可預期錯誤。"""


_STORE_COLUMNS = [
    "store_id",
    "brand_id",
    "store_name",
    "store_name_zh",
    "store_code",
    "is_active",
    "created_at",
    "updated_at",
    "updated_by",
]

_BRAND_COLUMNS = [
    "brand_id",
    "brand_name",
    "brand_name_zh",
    "is_active",
]


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def norm_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    work = df.copy()
    for col in columns:
        if col not in work.columns:
            work[col] = ""
    return work


def safe_active_series(df: pd.DataFrame, col: str = "is_active") -> pd.Series:
    if col not in df.columns:
        return pd.Series([1] * len(df), index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(1).astype(int)


def load_store_admin_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    tables = sheet_read_many(["stores", "brands"])
    stores_df = tables.get("stores", pd.DataFrame()).copy()
    brands_df = tables.get("brands", pd.DataFrame()).copy()

    if stores_df.empty:
        stores_df = pd.DataFrame(columns=_STORE_COLUMNS)
    stores_df = ensure_columns(stores_df, _STORE_COLUMNS)

    if brands_df.empty:
        brands_df = pd.DataFrame(columns=_BRAND_COLUMNS)
    brands_df = ensure_columns(brands_df, _BRAND_COLUMNS)

    stores_df["store_id"] = stores_df["store_id"].apply(norm_text)
    stores_df["brand_id"] = stores_df["brand_id"].apply(norm_text)
    stores_df["store_name"] = stores_df["store_name"].apply(norm_text)
    stores_df["store_name_zh"] = stores_df["store_name_zh"].apply(norm_text)
    stores_df["store_code"] = stores_df["store_code"].apply(lambda x: norm_text(x).upper())
    stores_df["is_active"] = safe_active_series(stores_df)

    brands_df["brand_id"] = brands_df["brand_id"].apply(norm_text)
    brands_df["brand_name"] = brands_df["brand_name"].apply(norm_text)
    brands_df["brand_name_zh"] = brands_df["brand_name_zh"].apply(norm_text)
    brands_df["is_active"] = safe_active_series(brands_df)
    return stores_df, brands_df


def pick_first_existing_column(df: pd.DataFrame, candidates: list[str], fallback: str) -> str:
    for col in candidates:
        if col in df.columns:
            return col
    return fallback


def build_store_admin_view(stores_df: pd.DataFrame, brands_df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    brand_label_col = pick_first_existing_column(brands_df, ["brand_name_zh", "brand_name"], "brand_id")
    brand_map = brands_df[["brand_id", brand_label_col]].copy()
    brand_map = brand_map.rename(columns={brand_label_col: "brand_display"})
    brand_map["brand_display"] = brand_map["brand_display"].apply(norm_text).replace("", pd.NA)

    stores_view = stores_df.merge(brand_map, on="brand_id", how="left")
    stores_view["brand_display"] = stores_view["brand_display"].fillna("未設定品牌")
    stores_view["store_display"] = (
        stores_view["store_name_zh"].replace("", pd.NA).fillna(stores_view["store_name"])
    )
    stores_view["status_text"] = stores_view["is_active"].map({1: "啟用", 0: "停用"}).fillna("未設定")
    stores_view = stores_view.sort_values(
        by=["store_code", "store_id"], ascending=[True, True], na_position="last"
    ).reset_index(drop=True)
    return stores_view, brand_label_col


def generate_next_store_code(stores_df: pd.DataFrame) -> str:
    if stores_df.empty or "store_code" not in stores_df.columns:
        return "S001"

    used_numbers = []
    for code in stores_df["store_code"].astype(str).str.strip().str.upper().tolist():
        if code.startswith("S") and len(code) >= 2 and code[1:].isdigit():
            used_numbers.append(int(code[1:]))
    next_num = 1 if not used_numbers else max(used_numbers) + 1
    return f"S{next_num:03d}"


def build_brand_options(brands_df: pd.DataFrame, brand_label_col: str) -> tuple[list[str], dict[str, str]]:
    active_brands_df = brands_df[brands_df["is_active"] == 1].copy()
    options = (
        active_brands_df["brand_id"].astype(str).str.strip().replace("", pd.NA).dropna().tolist()
    )
    label_map = (
        active_brands_df.set_index("brand_id")[brand_label_col].apply(norm_text).to_dict()
        if not active_brands_df.empty and brand_label_col in active_brands_df.columns
        else {}
    )
    return options, label_map


def create_store(brand_id: str, store_name_zh: str, actor: str = "system") -> dict:
    stores_df, _ = load_store_admin_tables()
    brand_id = norm_text(brand_id)
    store_name_zh = norm_text(store_name_zh)

    if not brand_id:
        raise StoreServiceError("品牌不可為空")
    if not store_name_zh:
        raise StoreServiceError("中文分店名稱不可為空")

    existing_names = stores_df["store_name_zh"].apply(norm_text).tolist()
    if store_name_zh in existing_names:
        raise StoreServiceError("中文分店名稱已存在，請確認是否重複建立")

    try:
        new_store_id = allocate_store_id()
    except Exception as e:
        raise StoreServiceError(f"store_id 產生失敗：{e}")

    new_store_code = generate_next_store_code(stores_df)
    new_row = {
        "store_id": new_store_id,
        "brand_id": brand_id,
        "store_name": store_name_zh,
        "store_name_zh": store_name_zh,
        "store_code": new_store_code,
        "is_active": 1,
        "created_at": now_ts(),
        "updated_at": "",
        "updated_by": "",
    }

    header = sheet_get_header("stores")
    sheet_append("stores", header, [new_row])
    sheet_bust_cache()

    audit_log(
        action="create_store",
        entity_id=new_store_id,
        before=None,
        after=new_row,
        note=f"建立分店：{store_name_zh}",
    )
    return new_row


def write_back_stores_df(stores_df: pd.DataFrame):
    stores_header = sheet_get_header("stores")
    work = stores_df.copy()
    for col in stores_header:
        if col not in work.columns:
            work[col] = ""
    work = work[stores_header].copy()
    rows = work.fillna("").astype(str).values.tolist()
    sheet_replace_table("stores", stores_header, rows)


def update_store_active(store_id: str, new_active: int, actor: str = "system"):
    stores_df, _ = load_store_admin_tables()
    if stores_df.empty:
        raise StoreServiceError("stores 表沒有資料")

    target_store_id = norm_text(store_id)
    mask = stores_df["store_id"].astype(str).str.strip() == target_store_id
    if not mask.any():
        raise StoreServiceError(f"找不到分店：{target_store_id}")

    before_row = stores_df.loc[mask].iloc[0].to_dict()
    updates = {"is_active": int(new_active)}
    if "updated_at" in stores_df.columns:
        updates["updated_at"] = now_ts()
    if "updated_by" in stores_df.columns:
        updates["updated_by"] = actor

    sheet_update("stores", "store_id", target_store_id, updates)
    sheet_bust_cache()

    stores_df_after, _ = load_store_admin_tables()
    after_mask = stores_df_after["store_id"].astype(str).str.strip() == target_store_id
    after_row = stores_df_after.loc[after_mask].iloc[0].to_dict()
    audit_log(
        action="update_store_active",
        entity_id=target_store_id,
        before=before_row,
        after=after_row,
        note=f"更新分店狀態為：{'啟用' if int(new_active) == 1 else '停用'}",
    )
    return after_row


__all__ = [
    "StoreServiceError",
    "build_brand_options",
    "build_store_admin_view",
    "create_store",
    "generate_next_store_code",
    "load_store_admin_tables",
    "norm_text",
    "update_store_active",
]
