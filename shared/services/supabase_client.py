from __future__ import annotations

import streamlit as st
from supabase import create_client

DEFAULT_SUPABASE_URL = "https://hikmpynwpqtbgqhsuyqd.supabase.co"
DEFAULT_SUPABASE_KEY = "sb_publishable_NnWCl-WgBU2BqHFZLgdCEQ_2QNQwxd-"


def _get_secret(name: str, default: str = "") -> str:
    try:
        if hasattr(st, "secrets") and name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    return str(default).strip()


def get_supabase_url() -> str:
    return _get_secret("SUPABASE_URL", DEFAULT_SUPABASE_URL)


def get_supabase_key() -> str:
    return _get_secret("SUPABASE_KEY", DEFAULT_SUPABASE_KEY)


supabase = create_client(get_supabase_url(), get_supabase_key())


def fetch_table(table_name: str):
    res = supabase.table(table_name).select("*").execute()
    return res.data or []


def insert_rows(table_name: str, rows: list[dict]):
    if not rows:
        return None
    return supabase.table(table_name).insert(rows).execute()


def update_rows(table_name: str, filters: dict, updates: dict):
    query = supabase.table(table_name).update(updates)
    for field, value in (filters or {}).items():
        query = query.eq(field, value)
    return query.execute()


def upsert_rows(table_name: str, rows: list[dict], on_conflict: str | None = None):
    if not rows:
        return None
    kwargs = {}
    if on_conflict:
        kwargs["on_conflict"] = on_conflict
    return supabase.table(table_name).upsert(rows, **kwargs).execute()


def delete_rows(table_name: str, filters: dict):
    query = supabase.table(table_name).delete()
    for field, value in (filters or {}).items():
        query = query.eq(field, value)
    return query.execute()


def replace_table_rows(table_name: str, key_field: str, rows: list[dict]):
    existing = fetch_table(table_name)
    existing_keys = {str(r.get(key_field, "")).strip() for r in existing if str(r.get(key_field, "")).strip()}
    new_keys = {str(r.get(key_field, "")).strip() for r in rows if str(r.get(key_field, "")).strip()}

    delete_keys = [k for k in existing_keys if k and k not in new_keys]
    for key in delete_keys:
        supabase.table(table_name).delete().eq(key_field, key).execute()

    if rows:
        supabase.table(table_name).upsert(rows).execute()
    return True
