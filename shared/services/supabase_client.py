from __future__ import annotations

import os
from typing import Any

import streamlit as st
from supabase import create_client


def _get_secret(name: str, default: str = "") -> str:
    try:
        if hasattr(st, "secrets"):
            if name in st.secrets:
                return str(st.secrets[name])
            lower = name.lower()
            if lower in st.secrets:
                return str(st.secrets[lower])
    except Exception:
        pass
    return os.getenv(name, default)


SUPABASE_URL = _get_secret("SUPABASE_URL", "https://hikmpynwpqtbgqhsuyqd.supabase.co")
SUPABASE_KEY = _get_secret("SUPABASE_KEY", "sb_publishable_NnWCl-WgBU2BqHFZLgdCEQ_2QNQwxd-")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def _clean_scalar(value: Any):
    if value is None:
        return None
    if isinstance(value, float):
        return value
    text = str(value).strip() if not isinstance(value, (int, bool)) else value
    if text == "":
        return None
    return value


def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
    return {str(k): _clean_scalar(v) for k, v in row.items()}


def fetch_table(table_name: str):
    res = supabase.table(table_name).select("*").execute()
    return res.data or []


def insert_rows(table_name: str, rows: list[dict[str, Any]]):
    payload = [_clean_row(r) for r in rows if isinstance(r, dict)]
    if not payload:
        return None
    return supabase.table(table_name).insert(payload).execute()


def update_rows_by_match(table_name: str, key_field: str, key_value: Any, updates: dict[str, Any]):
    payload = _clean_row(updates or {})
    return supabase.table(table_name).update(payload).eq(key_field, key_value).execute()


def delete_rows_by_match(table_name: str, key_field: str, key_value: Any):
    return supabase.table(table_name).delete().eq(key_field, key_value).execute()
