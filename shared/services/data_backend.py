from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from shared.services.supabase_client import delete_rows, fetch_table, insert_rows, update_rows
from shared.services.table_contract import TABLE_CONTRACT

from shared.utils.common_helpers import _norm

BASE_DIR = Path(__file__).resolve().parent
LOCAL_SERVICE_ACCOUNT = BASE_DIR / "service_account.json"


def _get_runtime_table_cache() -> dict:
    """
    取得本次使用者 session 的表格快取。
    目的：
    1. 同一次操作流程中，避免同一張表被重複打到 Supabase。
    2. 當遠端暫時無法存取時，優先回傳最近一次成功資料，降低整頁爆掉機率。
    """
    return st.session_state.setdefault("_runtime_table_cache", {})


def _get_runtime_header_cache() -> dict:
    """取得本次使用者 session 的表頭快取。"""
    return st.session_state.setdefault("_runtime_header_cache", {})


def _get_runtime_sheet_snapshot_cache() -> dict:
    """統一保存同一版本 table 的 header/table 原始快照，避免重複遠端讀取。"""
    return st.session_state.setdefault("_runtime_sheet_snapshot_cache", {})


def _get_table_version_map() -> dict:
    """每張表各自的快取版本號。"""
    return st.session_state.setdefault("_table_cache_versions", {})


def get_table_version(sheet_name: str) -> int:
    versions = _get_table_version_map()
    key = _norm(sheet_name)
    return int(versions.get(key, 0))


def get_table_versions(sheet_names: list[str] | tuple[str, ...]) -> tuple[int, ...]:
    return tuple(get_table_version(name) for name in sheet_names)


def _table_versions_signature(sheet_names: list[str] | tuple[str, ...]) -> tuple[tuple[str, int], ...]:
    """把多張表目前版本整理成可比較的簽章，供衍生資料快取使用。"""
    return tuple((str(name).strip(), get_table_version(name)) for name in sheet_names)


def _get_runtime_df_cache() -> dict:
    """取得 session 內衍生 DataFrame 快取。"""
    return st.session_state.setdefault("_runtime_df_cache", {})


def _session_df_cache_get(cache_key: str, signature) -> pd.DataFrame | None:
    """若簽章相同，直接回傳衍生 DataFrame 快取。"""
    cache = _get_runtime_df_cache()
    hit = cache.get(cache_key)
    if isinstance(hit, dict) and hit.get("signature") == signature:
        df = hit.get("df")
        if isinstance(df, pd.DataFrame):
            return df.copy()
    return None


def _session_df_cache_set(cache_key: str, signature, df: pd.DataFrame):
    """寫入 session 內衍生 DataFrame 快取。"""
    cache = _get_runtime_df_cache()
    cache[cache_key] = {
        "signature": signature,
        "df": df.copy(),
    }


def _read_table_remote(sheet_name: str, version: int = 0) -> pd.DataFrame:
    """主資料來源：Supabase。"""
    rows = fetch_table(sheet_name)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame()

    df.columns = [_norm(c) for c in df.columns]

    df = df[
        df.apply(lambda r: any(_norm(v) != "" for v in r), axis=1)
    ].reset_index(drop=True)

    return df

def _get_header_remote(sheet_name: str, version: int = 0) -> list[str]:
    """從 Supabase 讀取 header。"""
    rows = fetch_table(sheet_name)
    if rows:
        df = pd.DataFrame(rows)
        if not df.empty:
            header = [_norm(c) for c in df.columns]
            if header:
                return header
    raise ValueError(f"{sheet_name} 沒有 header")


def _resolve_table_version(sheet_name: str, force_refresh: bool = False) -> tuple[str, int]:
    cache_key = _norm(sheet_name)
    versions = _get_table_version_map()
    if force_refresh:
        versions[cache_key] = get_table_version(sheet_name) + 1
    return cache_key, get_table_version(sheet_name)


def read_table(sheet_name: str, force_refresh: bool = False) -> pd.DataFrame:
    """
    讀取資料表。主資料來源：Supabase。
    三層快取：
    1. cache_resource：client 連線共用
    2. cache_data + session snapshot：同張表 header/table 共用一次遠端讀取
    3. session_state runtime cache：同一位使用者當前操作流程直接重用 DataFrame
    """
    cache = _get_runtime_table_cache()
    cache_key, current_version = _resolve_table_version(sheet_name, force_refresh=force_refresh)

    if force_refresh:
        cache.pop(cache_key, None)
        _get_runtime_sheet_snapshot_cache().pop(cache_key, None)

    cached = cache.get(cache_key)
    if isinstance(cached, dict) and cached.get("version") == current_version:
        return cached.get("df", pd.DataFrame()).copy()

    try:
        df = _read_table_remote(sheet_name, current_version)
        cache[cache_key] = {"version": current_version, "df": df.copy()}
        return df.copy()
    except Exception as e:
        old_df = None
        if isinstance(cached, dict):
            old_df = cached.get("df")
        elif cached is not None:
            old_df = cached

        if old_df is not None:
            st.warning(f"{sheet_name} 讀取失敗，已改用暫存資料：{e}")
            return old_df.copy()

        st.warning(f"{sheet_name} 讀取失敗：{e}")
        return pd.DataFrame()


def get_header(sheet_name: str, force_refresh: bool = False) -> list[str]:
    cache = _get_runtime_header_cache()
    cache_key, current_version = _resolve_table_version(sheet_name, force_refresh=force_refresh)

    if force_refresh:
        cache.pop(cache_key, None)
        _get_runtime_sheet_snapshot_cache().pop(cache_key, None)

    cached = cache.get(cache_key)
    if isinstance(cached, dict) and cached.get("version") == current_version:
        return list(cached.get("header", []))

    try:
        header = _get_header_remote(sheet_name, current_version)
        cache[cache_key] = {"version": current_version, "header": list(header)}
        return list(header)
    except Exception as e:
        old_header = None
        if isinstance(cached, dict):
            old_header = cached.get("header")
        elif cached is not None:
            old_header = cached
        if old_header is not None:
            st.warning(f"{sheet_name} header 讀取失敗，已改用暫存資料：{e}")
            return list(old_header)
        # [TABLE_CONTRACT fallback] 所有遠端來源失敗時，從契約取 columns_order
        contract = TABLE_CONTRACT.get(_norm(sheet_name))
        if contract and contract.get("columns_order"):
            return list(contract["columns_order"])
        raise


# ---------------------------------------------------------------------------
# TABLE_CONTRACT 寫入前驗證（內部函式）
# table 不在 TABLE_CONTRACT 時一律略過，不拋錯，確保向後相容。
# ---------------------------------------------------------------------------

def _get_table_contract(table_name: str) -> dict | None:
    """回傳 table 的 contract 定義；未定義時回傳 None（略過驗證）。"""
    return TABLE_CONTRACT.get(_norm(table_name))


def _validate_required_columns(table_name: str, row: dict) -> None:
    """檢查 row 中 required_columns 不可缺少或為空。
    table 不在 TABLE_CONTRACT：直接略過。
    """
    contract = _get_table_contract(table_name)
    if contract is None:
        return
    required = contract.get("required_columns", [])
    missing = [
        col for col in required
        if col not in row or row[col] == "" or row[col] is None
    ]
    if missing:
        raise ValueError(
            f"[{table_name}] 寫入失敗：required_columns 缺少或為空 → {missing}"
        )


def _validate_primary_key_presence(table_name: str, row: dict) -> None:
    """檢查 row 中 primary_key 不可缺少或為空。
    table 不在 TABLE_CONTRACT：直接略過。
    """
    contract = _get_table_contract(table_name)
    if contract is None:
        return
    pk = contract.get("primary_key")
    if not pk:
        return
    if pk not in row or row.get(pk) == "" or row.get(pk) is None:
        raise ValueError(
            f"[{table_name}] 寫入失敗：primary_key「{pk}」缺少或為空"
        )


def append_rows_by_header(sheet_name: str, header: list[str], rows: list[dict]):
    if not rows:
        return

    normalized_rows: list[dict] = []
    for row in rows:
        if isinstance(row, dict):
            normalized_rows.append({col: row.get(col, "") for col in header})
        else:
            values = list(row)
            values = values[:len(header)] + [""] * max(0, len(header) - len(values))
            normalized_rows.append({col: values[idx] for idx, col in enumerate(header)})

    # [TABLE_CONTRACT 驗證] 寫入前檢查 required_columns 與 primary_key
    for row in normalized_rows:
        _validate_required_columns(sheet_name, row)
        _validate_primary_key_presence(sheet_name, row)

    # 省略空值欄位：避免 integer/numeric 欄位收到 "" 導致型別錯誤
    insert_payload = [
        {k: v for k, v in row.items() if v != "" and v is not None}
        for row in normalized_rows
    ]
    insert_rows(sheet_name, insert_payload)
    bust_cache(sheet_name)
    return


def get_row_index_map(sheet_name: str, key_field: str, force_refresh: bool = False) -> dict[str, int]:
    """建立 key -> 列號的快取映射，避免重複整張掃描。"""
    cache = st.session_state.setdefault("_runtime_row_index_cache", {})
    cache_key = f"{_norm(sheet_name)}::{_norm(key_field)}"
    current_version = get_table_version(sheet_name)

    if force_refresh:
        cache.pop(cache_key, None)

    cached = cache.get(cache_key)
    if isinstance(cached, dict) and cached.get("version") == current_version:
        return dict(cached.get("mapping", {}))

    df = read_table(sheet_name)
    mapping: dict[str, int] = {}
    if not df.empty and key_field in df.columns:
        keys = df[key_field].astype(str).str.strip().tolist()
        for idx, key in enumerate(keys, start=2):
            if key and key not in mapping:
                mapping[key] = idx

    cache[cache_key] = {"version": current_version, "mapping": dict(mapping)}
    return dict(mapping)


def update_row_by_match(sheet_name: str, key_field: str, key_value: str, updates: dict):
    """依指定鍵值更新單筆資料，寫入 Supabase。"""
    key_value = _norm(key_value)
    if not key_value:
        raise ValueError(f"{sheet_name}.{key_field} 不可為空")

    # [TABLE_CONTRACT 驗證] key_field 非 primary_key 時保留原行為不拋錯；
    # 若 updates 中明確帶有 primary_key，確保其值不為空。
    _contract = _get_table_contract(sheet_name)
    if _contract:
        _pk = _contract.get("primary_key")
        if _pk and _pk in (updates or {}):
            if (updates or {}).get(_pk) in ("", None):
                raise ValueError(
                    f"[{sheet_name}] 更新失敗：primary_key「{_pk}」在 updates 中不可為空"
                )

    # 保留 None（Supabase 接受 None 作為 NULL，空字串對 date/numeric 欄位會報錯）
    clean_updates = dict(updates or {})
    update_rows(sheet_name, {key_field: key_value}, clean_updates)
    bust_cache(sheet_name)


def delete_row_by_match(sheet_name: str, key_field: str, key_value: str):
    """依指定鍵值刪除單筆資料，寫入 Supabase。"""
    key_value = _norm(key_value)
    if not key_value:
        raise ValueError(f"{sheet_name}.{key_field} 不可為空")
    delete_rows(sheet_name, {key_field: key_value})
    bust_cache(sheet_name)


def _safe_clear_callable_cache(fn):
    clear_fn = getattr(fn, "clear", None)
    if callable(clear_fn):
        clear_fn()


def bust_cache(sheet_names: str | list[str] | tuple[str, ...] | None = None):
    """
    清除資料快取。

    規則：
    1. 不指定表名：維持舊行為，全部清掉
    2. 指定表名：只讓該表版本號 +1，並清除該表的 session 快取
    """
    if not sheet_names:
        _safe_clear_callable_cache(_read_table_remote)
        _safe_clear_callable_cache(_get_header_remote)
        st.session_state.pop("_runtime_table_cache", None)
        st.session_state.pop("_runtime_header_cache", None)
        st.session_state.pop("_runtime_row_index_cache", None)
        st.session_state.pop("_runtime_df_cache", None)
        st.session_state.pop("_runtime_sheet_snapshot_cache", None)
        st.session_state.pop("_table_cache_versions", None)
        return

    if isinstance(sheet_names, str):
        targets = [sheet_names]
    else:
        targets = list(sheet_names)

    table_cache = _get_runtime_table_cache()
    header_cache = _get_runtime_header_cache()
    snapshot_cache = _get_runtime_sheet_snapshot_cache()
    row_index_cache = st.session_state.setdefault("_runtime_row_index_cache", {})
    versions = _get_table_version_map()

    df_cache = st.session_state.setdefault("_runtime_df_cache", {})
    for name in targets:
        key = _norm(name)
        versions[key] = int(versions.get(key, 0)) + 1
        table_cache.pop(key, None)
        header_cache.pop(key, None)
        snapshot_cache.pop(key, None)
        prefix = f"{key}::"
        stale_keys = [k for k in list(row_index_cache.keys()) if str(k).startswith(prefix)]
        for stale_key in stale_keys:
            row_index_cache.pop(stale_key, None)

        stale_df_keys = []
        for cache_key, payload in list(df_cache.items()):
            sig = payload.get("signature") if isinstance(payload, dict) else None
            if not sig:
                continue
            try:
                if any(str(sheet_name).strip() == key for sheet_name, _version in sig):
                    stale_df_keys.append(cache_key)
            except Exception:
                continue
        for stale_df_key in stale_df_keys:
            df_cache.pop(stale_df_key, None)


# ---------------------------------------------------------------------------
# 以下為資料存取功能層，供 app_runtime / service_stores /
# order_write_utils 直接使用。
# ---------------------------------------------------------------------------

# TABLE_CONTRACT 已於頂部 import，此處直接建立 PK 查詢表
_PK_MAP: dict[str, str] = {
    t: info["primary_key"] for t, info in TABLE_CONTRACT.items() if info.get("primary_key")
}
_PK_MAP.update({
    "units":            "unit_id",
    "prices":           "price_id",
    "unit_conversions": "conversion_id",
    "transactions":     "txn_id",
    "audit_logs":       "audit_id",
    "settings":         "setting_key",
    "id_sequences":     "key",
})


def _pk_for_table(table: str, header: list[str] | None = None) -> str | None:
    """回傳資料表的 primary key 欄位名稱；找不到時嘗試從 header 推斷。"""
    key = _PK_MAP.get(_norm(table))
    if key:
        return key
    for col in (header or []):
        if str(col).strip().endswith("_id"):
            return str(col).strip()
    return None


def _rows_to_dicts(header: list[str], rows: list[list] | list[dict]) -> list[dict]:
    """將 list[list] 或 list[dict] 統一轉為 list[dict]（按 header 對齊）。"""
    out: list[dict] = []
    for row in rows:
        if isinstance(row, dict):
            out.append({col: row.get(col, "") for col in header})
        else:
            values = list(row)
            values = values[:len(header)] + [""] * max(0, len(header) - len(values))
            out.append({col: values[idx] for idx, col in enumerate(header)})
    return out


def read_many(table_names) -> dict[str, pd.DataFrame]:
    """批次讀取多張表，回傳 {table_name: DataFrame}。"""
    return {name: read_table(name) for name in table_names}


def read_row_maps(table: str) -> tuple[list[str], list[tuple[int, dict]]]:
    """
    讀取資料表，回傳 (header, [(row_num, row_dict), ...])。
    row_num 從 2 開始（與 Google Sheets 列號相容，header 為第 1 列）。
    """
    df = read_table(table).copy()
    if df is None or df.empty:
        return [], []
    header = [_norm(x) for x in list(df.columns)]
    row_maps: list[tuple[int, dict]] = []
    for row_num, (_, row) in enumerate(df.iterrows(), start=2):
        row_maps.append((row_num, {col: row.get(col, "") for col in header}))
    return header, row_maps


def find_row_number(table: str, key_field: str, key_value: str):
    """
    依 key_field == key_value 搜尋資料表，回傳 (row_num, header, row_dict)。
    找不到時回傳 (None, header, None)。
    """
    header, row_maps = read_row_maps(table)
    if not header:
        raise ValueError(f"{table} missing header")
    if key_field not in header:
        raise ValueError(f"{table} missing column: {key_field}")
    for row_num, row_dict in row_maps:
        if _norm(str(row_dict.get(key_field, ""))) == _norm(key_value):
            return row_num, header, row_dict
    return None, header, None


def update_row_values(
    table: str,
    row_num: int,
    header: list[str],
    row_values: list,
    value_input_option: str = "USER_ENTERED",
):
    """
    以 row_num（1-indexed，header = 1）定位列，將整列更新為 row_values。
    實際透過 primary key 執行 Supabase update。
    """
    if not header:
        raise ValueError(f"{table} missing header")

    normalized = list(row_values)
    normalized = normalized[:len(header)] + [""] * max(0, len(header) - len(normalized))

    df = read_table(table)
    idx = int(row_num) - 2
    if df is None or df.empty or idx < 0 or idx >= len(df):
        raise ValueError(f"{table} invalid row_num={row_num}")

    pk = _pk_for_table(table, list(df.columns))
    if not pk or pk not in df.columns:
        raise ValueError(f"{table} missing primary key for row update")

    row = df.iloc[idx].to_dict()
    for i, col in enumerate(header):
        row[col] = normalized[i]

    key_val = _norm(str(row.get(pk, "")))
    update_rows(table, {pk: key_val}, row)
    bust_cache(table)


def replace_table(table: str, header: list[str], rows: list[list] | list[dict]):
    """
    清空資料表後批次寫入新資料（按 primary key 逐筆刪除再 insert）。
    """
    records = _rows_to_dicts(header, rows)
    pk = _pk_for_table(table, header)

    if pk:
        existing = read_table(table)
        if existing is not None and not existing.empty and pk in existing.columns:
            for _, r in existing.iterrows():
                key_val = _norm(str(r.get(pk, "")))
                if key_val:
                    delete_rows(table, {pk: key_val})

    if records:
        insert_rows(table, records)
    bust_cache(table)


def clear_keep_header(table: str):
    """清空資料表所有資料列（保留欄位定義）。"""
    header = get_header(table)
    replace_table(table, header, [])
