from __future__ import annotations

import json
from pathlib import Path

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from shared.services.supabase_client import fetch_table, insert_rows, update_rows

from shared.utils.common_helpers import _norm

DEFAULT_SHEET_ID = "1L1ogNjLWjjH8usMWC2JQowMMZkfD4zkuE-4UcgiTqXQ"
BASE_DIR = Path(__file__).resolve().parent
LOCAL_SERVICE_ACCOUNT = BASE_DIR / "service_account.json"


def _get_secret_sheet_id() -> str:
    try:
        if hasattr(st.secrets, "get"):
            return st.secrets.get("SHEET_ID") or st.secrets.get("sheet_id") or DEFAULT_SHEET_ID
    except Exception:
        pass
    return DEFAULT_SHEET_ID


def _get_service_account_info() -> dict | None:
    """統一 Google Service Account 讀取入口。"""
    try:
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"])
        if "gcp" in st.secrets:
            return dict(st.secrets["gcp"])
        if LOCAL_SERVICE_ACCOUNT.exists():
            return json.loads(LOCAL_SERVICE_ACCOUNT.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


@st.cache_resource(show_spinner=False)
def _build_gspread_client(_service_account_signature: str):
    info = _get_service_account_info()
    if not info:
        raise ValueError("找不到 Google Service Account 設定")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def _open_spreadsheet_resource(_service_account_signature: str, sheet_id: str):
    client = _build_gspread_client(_service_account_signature)
    return client.open_by_key(sheet_id)


def get_gspread_client():
    """
    Google Sheets 驗證入口
    優先順序：
    1. st.secrets["gcp_service_account"]
    2. st.secrets["gcp"]
    3. 本機 service_account.json
    """
    try:
        info = _get_service_account_info()
        if not info:
            st.error("找不到 Google Service Account 設定")
            return None
        signature = json.dumps(info, ensure_ascii=False, sort_keys=True)
        return _build_gspread_client(signature)
    except Exception as e:
        st.error(f"Google Sheets 驗證失敗：{e}")
        return None


def get_spreadsheet():
    """取得目前主資料庫 Spreadsheet。"""
    try:
        info = _get_service_account_info()
        if not info:
            st.error("找不到 Google Service Account 設定")
            return None
        signature = json.dumps(info, ensure_ascii=False, sort_keys=True)
        return _open_spreadsheet_resource(signature, _get_secret_sheet_id())
    except Exception as e:
        st.error(f"開啟 Sheet 失敗：{e}")
        return None


def _get_runtime_table_cache() -> dict:
    """
    取得本次使用者 session 的表格快取。
    目的：
    1. 同一次操作流程中，避免同一張表被重複打到 Google Sheets。
    2. 當 Google API 暫時 429 時，優先回傳最近一次成功資料，降低整頁爆掉機率。
    """
    return st.session_state.setdefault("_runtime_table_cache", {})


def _get_runtime_header_cache() -> dict:
    """取得本次使用者 session 的表頭快取。"""
    return st.session_state.setdefault("_runtime_header_cache", {})


def _get_runtime_sheet_snapshot_cache() -> dict:
    """統一保存同一版本 sheet 的 header/table 原始快照，避免重複遠端讀取。"""
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


@st.cache_data(show_spinner=False)
def _read_sheet_snapshot_remote(sheet_name: str, version: int = 0) -> dict:
    """
    遠端讀表統一入口。
    同一張表在同一版號下，只打一次 Google Sheets，
    header / table 都共用同一份快照。
    """
    sh = get_spreadsheet()
    if sh is None:
        return {"header": [], "rows": []}

    ws = sh.worksheet(sheet_name)
    values = ws.get_all_values()
    if not values:
        return {"header": [], "rows": []}

    header = [_norm(c) for c in values[0]]
    rows = values[1:]
    normalized_rows: list[list[str]] = []
    for row in rows:
        current = list(row)
        if len(current) < len(header):
            current = current + [""] * (len(header) - len(current))
        else:
            current = current[:len(header)]
        normalized_rows.append(current)

    return {
        "header": header,
        "rows": normalized_rows,
    }


def _build_dataframe_from_snapshot(snapshot: dict) -> pd.DataFrame:
    header = list(snapshot.get("header", []) or [])
    rows = list(snapshot.get("rows", []) or [])

    if not header:
        return pd.DataFrame()
    if not rows:
        return pd.DataFrame(columns=header)

    df = pd.DataFrame(rows, columns=header)
    if not df.empty:
        df = df[
            df.apply(lambda r: any(_norm(v) != "" for v in r), axis=1)
        ].reset_index(drop=True)
    return df


def _get_sheet_snapshot(sheet_name: str, version: int = 0, force_refresh: bool = False) -> dict:
    cache = _get_runtime_sheet_snapshot_cache()
    cache_key = _norm(sheet_name)

    if force_refresh:
        cache.pop(cache_key, None)

    cached = cache.get(cache_key)
    if isinstance(cached, dict) and cached.get("version") == version:
        return {
            "version": version,
            "header": list(cached.get("header", []) or []),
            "rows": [list(row) for row in list(cached.get("rows", []) or [])],
        }

    snapshot = _read_sheet_snapshot_remote(sheet_name, version)
    normalized = {
        "version": version,
        "header": list(snapshot.get("header", []) or []),
        "rows": [list(row) for row in list(snapshot.get("rows", []) or [])],
    }
    cache[cache_key] = normalized
    return {
        "version": version,
        "header": list(normalized["header"]),
        "rows": [list(row) for row in normalized["rows"]],
    }


def _read_table_remote(sheet_name: str, version: int = 0) -> pd.DataFrame:
    """
    優先讀 Supabase。
    若 Supabase 讀不到，再退回原本 Google Sheets 流程。
    """
    try:
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
    except Exception:
        snapshot = _get_sheet_snapshot(sheet_name, version)
        return _build_dataframe_from_snapshot(snapshot)

def _get_header_remote(sheet_name: str, version: int = 0) -> list[str]:
    """
    優先讀 Supabase header。
    若 Supabase 失敗，再退回 Google Sheets header。
    """
    try:
        rows = fetch_table(sheet_name)
        if rows:
            df = pd.DataFrame(rows)
            if not df.empty:
                header = [_norm(c) for c in df.columns]
                if header:
                    return header
    except Exception:
        pass

    snapshot = _get_sheet_snapshot(sheet_name, version)
    header = list(snapshot.get("header", []) or [])
    if not header:
        raise ValueError(f"{sheet_name} 沒有 header")
    return header


def _resolve_table_version(sheet_name: str, force_refresh: bool = False) -> tuple[str, int]:
    cache_key = _norm(sheet_name)
    versions = _get_table_version_map()
    if force_refresh:
        versions[cache_key] = get_table_version(sheet_name) + 1
    return cache_key, get_table_version(sheet_name)


def read_table(sheet_name: str, force_refresh: bool = False) -> pd.DataFrame:
    """
    讀取 Google Sheet 表格。
    這裡採三層快取：
    1. cache_resource：client / spreadsheet 連線共用
    2. cache_data + session snapshot：同張表 header/table 共用一次遠端讀取
    3. session_state runtime cache：同一位使用者當前操作流程直接重用 DataFrame

    另外當 Google API 暫時 429 / timeout 時：
    - 若 session 內已有最近一次成功資料，優先回傳舊資料
    - 目的不是永久吃舊資料，而是避免單次畫面整頁炸掉
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
        raise


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

    try:
        insert_rows(sheet_name, normalized_rows)
        bust_cache(sheet_name)
        return
    except Exception:
        pass

    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet(sheet_name)
    values = [[row.get(col, "") for col in header] for row in normalized_rows]
    ws.append_rows(values, value_input_option="USER_ENTERED")


def get_row_index_map(sheet_name: str, key_field: str, force_refresh: bool = False) -> dict[str, int]:
    """建立 key -> Google Sheet 列號的快取映射，避免重複整張掃描。"""
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
    """依指定鍵值更新單筆資料，優先寫入 Supabase。"""
    key_value = _norm(key_value)
    if not key_value:
        raise ValueError(f"{sheet_name}.{key_field} 不可為空")

    try:
        clean_updates = {field: ("" if value is None else value) for field, value in (updates or {}).items()}
        update_rows(sheet_name, {key_field: key_value}, clean_updates)
        bust_cache(sheet_name)
        return
    except Exception:
        pass

    header = get_header(sheet_name)
    if not header:
        raise ValueError(f"{sheet_name} 沒有 header")

    row_map = get_row_index_map(sheet_name, key_field)
    row_idx = row_map.get(key_value)
    if row_idx is None:
        raise ValueError(f"找不到 {sheet_name}.{key_field} = {key_value}")

    df = read_table(sheet_name)
    if key_field not in df.columns:
        raise ValueError(f"{sheet_name} 缺少欄位 {key_field}")

    mask = df[key_field].astype(str).str.strip() == key_value
    if not mask.any():
        raise ValueError(f"找不到 {sheet_name}.{key_field} = {key_value}")

    row = df.loc[mask].iloc[0].to_dict()
    for col in header:
        row.setdefault(col, "")
    for field, value in (updates or {}).items():
        if field not in row:
            row[field] = ""
        row[field] = "" if value is None else value

    values = [[row.get(col, "") for col in header]]

    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet(sheet_name)

    def _col_letter(n: int) -> str:
        result = ''
        while n > 0:
            n, rem = divmod(n - 1, 26)
            result = chr(65 + rem) + result
        return result

    end_col = _col_letter(len(header))
    ws.update(f"A{row_idx}:{end_col}{row_idx}", values)
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
        _safe_clear_callable_cache(_build_gspread_client)
        _safe_clear_callable_cache(_open_spreadsheet_resource)
        _safe_clear_callable_cache(_read_sheet_snapshot_remote)
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
