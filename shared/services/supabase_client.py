from __future__ import annotations

import os

import streamlit as st

# ----------------------------------------------------------------
# 金鑰讀取：優先順序
#   1. st.secrets["SUPABASE_ANON_KEY"] / ["SUPABASE_URL"]
#   2. st.secrets["SUPABASE_KEY"]（向下相容）
#   3. 環境變數 SUPABASE_ANON_KEY / SUPABASE_URL
#   4. 找不到 → 呼叫時拋出明確錯誤，不直接 crash
# ----------------------------------------------------------------

def _get_secret(name: str) -> str:
    """從 st.secrets 讀取，失敗時回傳空字串。"""
    try:
        if hasattr(st, "secrets") and name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    return ""


def get_supabase_url() -> str:
    return (
        _get_secret("SUPABASE_URL")
        or os.environ.get("SUPABASE_URL", "")
    )


def get_supabase_service_role_key() -> str:
    """Service Role Key：繞過 RLS，供後端寫入使用。"""
    return (
        _get_secret("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    )


def get_supabase_key() -> str:
    """key 優先順序：service_role > anon > 舊版 SUPABASE_KEY。
    service_role key 繞過 RLS，適合後端寫入；若未設定則 fallback anon key。
    """
    return (
        get_supabase_service_role_key()
        or _get_secret("SUPABASE_ANON_KEY")
        or _get_secret("SUPABASE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY", "")
        or os.environ.get("SUPABASE_KEY", "")
    )


# ----------------------------------------------------------------
# 延遲初始化 client：避免 import 時即崩潰
# ----------------------------------------------------------------
_supabase_client = None


def _get_client():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    from supabase import create_client  # 延遲 import，避免無 supabase 套件時爆
    url = get_supabase_url()
    key = get_supabase_key()

    if not url or not key:
        raise ValueError(
            "Supabase 未設定：請在 .streamlit/secrets.toml 加入\n"
            "  SUPABASE_URL = \"...\"\n"
            "  SUPABASE_ANON_KEY = \"...\""
        )

    _supabase_client = create_client(url, key)
    return _supabase_client


def fetch_table(table_name: str):
    _PAGE_SIZE = 1000
    all_rows: list = []
    start = 0
    while True:
        res = _get_client().table(table_name).select("*").range(start, start + _PAGE_SIZE - 1).execute()
        batch = res.data or []
        all_rows.extend(batch)
        if len(batch) < _PAGE_SIZE:
            break
        start += _PAGE_SIZE
    return all_rows


def insert_rows(table_name: str, rows: list[dict]):
    if not rows:
        return None
    return _get_client().table(table_name).insert(rows).execute()


def update_rows(table_name: str, filters: dict, updates: dict):
    query = _get_client().table(table_name).update(updates)
    for field, value in (filters or {}).items():
        query = query.eq(field, value)
    return query.execute()


def upsert_rows(table_name: str, rows: list[dict], on_conflict: str | None = None):
    if not rows:
        return None
    kwargs = {}
    if on_conflict:
        kwargs["on_conflict"] = on_conflict
    return _get_client().table(table_name).upsert(rows, **kwargs).execute()


def delete_rows(table_name: str, filters: dict):
    query = _get_client().table(table_name).delete()
    for field, value in (filters or {}).items():
        query = query.eq(field, value)
    return query.execute()


def replace_table_rows(table_name: str, key_field: str, rows: list[dict]):
    client = _get_client()
    existing = fetch_table(table_name)
    existing_keys = {str(r.get(key_field, "")).strip() for r in existing if str(r.get(key_field, "")).strip()}
    new_keys = {str(r.get(key_field, "")).strip() for r in rows if str(r.get(key_field, "")).strip()}

    delete_keys = [k for k in existing_keys if k and k not in new_keys]
    for key in delete_keys:
        client.table(table_name).delete().eq(key_field, key).execute()

    if rows:
        client.table(table_name).upsert(rows).execute()
    return True


# ----------------------------------------------------------------
# [TEMP DEBUG] 連線診斷：確認 URL / Key / id_sequences 狀態
# 供 app_shell.py sidebar 呼叫，確認後可移除此函式
# ----------------------------------------------------------------
def debug_connection_info() -> dict:
    """[TEMP] 診斷 Supabase 連線狀態與 id_sequences 初始化。"""
    url = get_supabase_url()
    key = get_supabase_key()

    # 遮罩 URL：只顯示 https://xxxxxx...後6碼
    if url and len(url) > 20:
        masked_url = url[:12] + "..." + url[-6:]
    else:
        masked_url = url or "(未設定)"

    has_key = "yes" if key else "no"

    seq_exists = False
    seq_count = 0
    stocktake_seq = False
    order_seq = False
    stock_seq = False
    error_msg = ""

    try:
        rows = fetch_table("id_sequences")
        seq_exists = True
        seq_count = len(rows) if rows else 0
        if rows:
            seq_keys = {str(r.get("key", "")).strip() for r in rows}
            stocktake_seq = "stocktakes" in seq_keys
            order_seq = "purchase_orders" in seq_keys
            stock_seq = (
                "stocktake_lines" in seq_keys
                or "purchase_order_lines" in seq_keys
            )
    except Exception as e:
        error_msg = str(e)

    return {
        "masked_url": masked_url,
        "has_key": has_key,
        "seq_exists": seq_exists,
        "seq_count": seq_count,
        "stocktake_seq": stocktake_seq,
        "order_seq": order_seq,
        "stock_seq": stock_seq,
        "error_msg": error_msg,
    }
