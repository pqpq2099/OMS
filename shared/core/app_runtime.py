from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from shared.core.navigation import goto
import users_permissions.pages as users_permissions_pages
from users_permissions.services.service_users import (
    UserServiceError,
    authenticate_owner,
    load_users_df,
    norm_10,
    norm_text,
)
from shared.services.data_backend import (
    bust_cache as sheet_bust_cache,
    clear_keep_header as sheet_clear_keep_header,
    find_row_number as sheet_find_row_number,
    get_header,
    get_table_versions as sheet_get_versions,
    read_table as sheet_read,
    replace_table as sheet_replace_table,
    update_row_values as sheet_update_row_values,
)

def _read_login_enabled_setting() -> str:
    """從 settings 讀取 login_enabled，預設為 1（啟用登入）。"""
    try:
        versions = sheet_get_versions(("settings",))
        cache = st.session_state.get("_settings_login_enabled_cache")
        if isinstance(cache, dict) and cache.get("versions") == versions:
            value = str(cache.get("value", "1")).strip()
            return value if value in {"0", "1"} else "1"

        settings_df = sheet_read("settings").copy()
        if settings_df.empty:
            return "1"

        settings_df.columns = [str(c).strip() for c in settings_df.columns]

        key_col = None
        value_col = None

        for c in ["key", "setting_key", "name", "setting_name"]:
            if c in settings_df.columns:
                key_col = c
                break

        for c in ["value", "setting_value", "setting", "setting_val"]:
            if c in settings_df.columns:
                value_col = c
                break

        if not key_col or not value_col:
            return "1"

        hit = settings_df[
            settings_df[key_col].astype(str).str.strip().str.lower() == "login_enabled"
        ]
        if hit.empty:
            return "1"

        value = str(hit.iloc[0][value_col]).strip()
        final_value = value if value in {"0", "1"} else "1"
        st.session_state["_settings_login_enabled_cache"] = {
            "versions": versions,
            "value": final_value,
        }
        return final_value

    except Exception:
        return "1"


def _clear_login_session_state():
    """清除登入相關 session，切換登入模式後使用。"""
    login_keys = [
        "login_user",
        "login_account_code",
        "login_display_name",
        "login_role_id",
        "login_store_scope",
        "force_change_password",
        "login_bypass_mode",
        "role",
    ]
    for key in login_keys:
        st.session_state.pop(key, None)


def _ensure_login_session_when_disabled():
    """當 login_enabled = 0 時，自動建立免登入模式的 owner session。"""
    st.session_state["login_user"] = "BYPASS_OWNER"
    st.session_state["login_account_code"] = "bypass_owner"
    st.session_state["login_display_name"] = "免登入模式"
    st.session_state["login_role_id"] = "owner"
    st.session_state["login_store_scope"] = "ALL"
    st.session_state["force_change_password"] = False
    st.session_state["login_bypass_mode"] = True
    st.session_state["role"] = "owner"


def _is_bypass_mode() -> bool:
    """目前是否為免登入模式。"""
    return bool(st.session_state.get("login_bypass_mode", False))


def _has_locked_system_access() -> bool:
    """只有在免登入模式下，才需要額外驗證系統維護 / 系統工具。"""
    if not _is_bypass_mode():
        return True
    return bool(st.session_state.get("owner_gate_verified", False))


def _clear_locked_system_access():
    """清除系統維護 / 系統工具的額外驗證狀態。"""
    for key in ["owner_gate_verified", "owner_gate_display_name", "owner_gate_user_id", "owner_gate_return_step"]:
        st.session_state.pop(key, None)


def _go_owner_verify(return_step: str):
    """導向 Owner 驗證頁。"""
    st.session_state["owner_gate_return_step"] = return_step
    goto("owner_verify")


def _check_owner_password(account: str, password: str) -> tuple[bool, str]:
    """驗證 owner 帳號密碼。"""
    try:
        user_row = authenticate_owner(account, password)
    except UserServiceError as e:
        return False, str(e)

    st.session_state["owner_gate_verified"] = True
    st.session_state["owner_gate_display_name"] = norm_text(user_row.get("display_name"))
    st.session_state["owner_gate_user_id"] = norm_text(user_row.get("user_id"))
    return True, ""


def _render_locked_system_login_required(page_title: str) -> bool:
    """若目前為免登入模式，則在進入指定頁面前要求 owner 再驗證一次。"""
    if _has_locked_system_access():
        return True

    st.warning(f"{page_title} 需要先登入系統擁有者帳號才能查看。")
    if st.button("🔐 前往系統管理登入", width="stretch", key=f"goto_owner_verify_{page_title}"):
        _go_owner_verify(st.session_state.get("step", "select_store"))
    return False


def page_owner_verify():
    """免登入模式下，進入系統維護 / 系統工具前的 owner 驗證頁。"""
    st.title("🔐 系統管理登入")
    st.info("目前為免登入模式。只有系統擁有者登入後，才能查看系統維護與系統工具。")

    with st.form("owner_verify_form"):
        account = st.text_input("Owner 帳號", key="owner_verify_account")
        password = st.text_input("Owner 密碼", type="password", key="owner_verify_password")
        submitted = st.form_submit_button("登入並進入", use_container_width=True)

    if submitted:
        ok, err = _check_owner_password(account, password)
        if not ok:
            st.error(err)
        else:
            next_step = st.session_state.get("owner_gate_return_step", "select_store")
            st.success("驗證成功。")
            goto(next_step)

    if st.button("⬅️ 返回", width="stretch", key="back_from_owner_verify"):
        goto("select_store")


def ensure_login_ready():
    """確認登入模式與登入狀態，必要時導向登入頁。"""
    login_enabled = _read_login_enabled_setting()

    if login_enabled == "0":
        _ensure_login_session_when_disabled()
        return

    if "login_user" not in st.session_state:
        users_permissions_pages.page_login()
        st.stop()

    if st.session_state.get("force_change_password", False):
        users_permissions_pages.page_login()
        st.stop()


# ============================================================
# [A1] Session State 初始化
# 你最常改的地方之一：
# 1. 新增新的 session_state 欄位
# 2. 調整預設 step
# 3. 之後接正式登入角色時，會在這裡改 role 預設值
# ============================================================
def init_session():
    if "step" not in st.session_state:
        st.session_state.step = "select_store"
    if "record_date" not in st.session_state:
        st.session_state.record_date = date.today()
    if "store_id" not in st.session_state:
        st.session_state.store_id = ""
    if "store_name" not in st.session_state:
        st.session_state.store_name = ""
    if "vendor_id" not in st.session_state:
        st.session_state.vendor_id = ""
    if "vendor_name" not in st.session_state:
        st.session_state.vendor_name = ""

    # 舊頁面仍可能讀取 role，這裡同步正式登入角色，避免抓到錯誤預設值
    if "role" not in st.session_state:
        st.session_state.role = st.session_state.get("login_role_id", "")
    else:
        st.session_state.role = st.session_state.get("login_role_id", st.session_state.role)



def initialize_runtime():
    """初始化共用執行環境。"""
    ensure_login_ready()
    init_session()


# ============================================================
# [A2] 系統設定讀取/儲存輔助
# 這一區主要負責：
# 1. 從 settings 表抓 system_name 等設定
# 2. 找到 key / value 欄位
# 3. 存回 Google Sheets
# 如果之後要增加更多系統設定，先看這一區。
# ============================================================
def _get_settings_key_value_cols(settings_df: pd.DataFrame) -> tuple[str | None, str | None]:
    work = settings_df.copy()
    work.columns = [str(c).strip() for c in work.columns]

    key_col = None
    value_col = None

    for c in ["key", "setting_key", "name", "setting_name"]:
        if c in work.columns:
            key_col = c
            break

    for c in ["value", "setting_value", "setting", "setting_val"]:
        if c in work.columns:
            value_col = c
            break

    return key_col, value_col


def get_settings_dict() -> dict[str, str]:
    try:
        settings_df = sheet_read("settings")
        if settings_df.empty:
            return {}

        work = settings_df.copy()
        work.columns = [str(c).strip() for c in work.columns]

        key_col, value_col = _get_settings_key_value_cols(work)
        if not key_col or not value_col:
            return {}

        result: dict[str, str] = {}
        for _, row in work.iterrows():
            key = str(row.get(key_col, "")).strip()
            if not key:
                continue
            result[key] = str(row.get(value_col, "")).strip()
        return result

    except Exception:
        return {}



def get_login_enabled_status() -> str:
    """回傳標準化後的 login_enabled 狀態，只會是 0 或 1。"""
    value = _read_login_enabled_setting()
    return value if value in {"0", "1"} else "1"


def require_locked_system_page(page_title: str) -> bool:
    """系統頁面進入前的共用 gate 介面。"""
    return _render_locked_system_login_required(page_title)

def get_setting_value(setting_key: str, default: str = "") -> str:
    settings_map = get_settings_dict()
    return settings_map.get(setting_key, default)


def get_system_name() -> str:
    default_name = "營運管理系統"
    value = get_setting_value("system_name", default_name)
    return value if str(value).strip() else default_name


def save_setting(setting_key: str, setting_value: str):

    settings_df = sheet_read("settings").copy()

    # 如果完全沒有資料
    if settings_df.empty:
        settings_df = pd.DataFrame({
            "setting_key": [setting_key],
            "setting_value": [setting_value],
        })

    else:

        settings_df.columns = [str(c).strip() for c in settings_df.columns]

        key_col = None
        value_col = None

        for c in ["key", "setting_key", "name", "setting_name"]:
            if c in settings_df.columns:
                key_col = c
                break

        for c in ["value", "setting_value", "setting", "setting_val"]:
            if c in settings_df.columns:
                value_col = c
                break

        if not key_col or not value_col:
            raise ValueError("settings 表找不到 key/value 欄位")

        mask = (
            settings_df[key_col]
            .astype(str)
            .str.strip()
            .str.lower()
            == setting_key.lower()
        )

        if mask.any():
            settings_df.loc[mask, value_col] = setting_value
        else:
            new_row = {c: "" for c in settings_df.columns}
            new_row[key_col] = setting_key
            new_row[value_col] = setting_value
            settings_df = pd.concat(
                [settings_df, pd.DataFrame([new_row])],
                ignore_index=True
            )

    rows = settings_df.fillna("").astype(str).values.tolist()
    # TIMESTAMP 欄不可傳入 ""（PostgreSQL 22007），改回 None → SQL NULL
    _ts_cols = {i for i, c in enumerate(settings_df.columns) if c in ("updated_at", "created_at")}
    if _ts_cols:
        rows = [
            [None if (ci in _ts_cols and v == "") else v for ci, v in enumerate(row)]
            for row in rows
        ]
    sheet_replace_table("settings", settings_df.columns.tolist(), rows)


def _worksheet_clear_keep_header(sheet_name: str):
    sheet_clear_keep_header(sheet_name)


def _reset_sequence_keys(target_keys: list[str], next_value: int = 1, actor: str = "owner"):
    df = sheet_read("id_sequences").copy()
    if df.empty:
        raise ValueError("id_sequences 沒有資料")

    header = [str(c).strip() for c in df.columns]
    if "key" not in header or "next_value" not in header:
        raise ValueError("id_sequences 缺少必要欄位")

    target_key_set = {str(k).strip() for k in target_keys if str(k).strip()}
    found_keys = set()
    now_ts = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    for row_key in sorted(target_key_set):
        row_num, header2, row_dict = sheet_find_row_number("id_sequences", "key", row_key)
        if row_num is None or not row_dict:
            continue

        candidate = {col: row_dict.get(col, "") for col in header2}
        candidate["next_value"] = str(int(next_value))
        if "updated_at" in candidate:
            candidate["updated_at"] = now_ts
        if "updated_by" in candidate:
            candidate["updated_by"] = actor

        sheet_update_row_values("id_sequences", row_num, header2, [candidate.get(col, "") for col in header2])
        found_keys.add(row_key)

    missing_keys = sorted(target_key_set - found_keys)
    if missing_keys:
        raise ValueError(f"id_sequences 找不到 key：{', '.join(missing_keys)}")


def _load_id_sequences_view() -> pd.DataFrame:
    df = sheet_read("id_sequences").copy()
    if df.empty:
        return df

    cols = [c for c in ["key", "env", "prefix", "width", "next_value", "updated_at", "updated_by"] if c in df.columns]
    if cols:
        df = df[cols].copy()
    return df.reset_index(drop=True)



def get_login_toggle_state() -> dict[str, str]:
    """回傳 system_tools 登入開關顯示所需狀態。"""
    current_login_enabled = get_login_enabled_status()
    if current_login_enabled == "1":
        return {
            "current": "1",
            "next": "0",
            "status_level": "success",
            "status_text": "目前狀態：登入畫面啟用中",
            "toggle_label": "🔓 一鍵關閉登入畫面",
            "toggle_help": "關閉後，系統會略過帳號密碼，直接以免登入模式進入。",
        }
    return {
        "current": "0",
        "next": "1",
        "status_level": "warning",
        "status_text": "目前狀態：登入畫面已關閉（免登入模式）",
        "toggle_label": "🔐 一鍵開啟登入畫面",
        "toggle_help": "開啟後，系統會恢復帳號密碼登入。",
    }


def update_login_enabled_setting(next_value: str):
    save_setting("login_enabled", next_value)
    sheet_bust_cache()
    st.session_state.pop("_settings_login_enabled_cache", None)
    clear_login_session_state()
    goto("select_store")


def refresh_runtime_sheet_cache():
    sheet_bust_cache()


def save_system_appearance(*, system_name: str, logo_url: str):
    save_setting("system_name", system_name.strip() or "營運管理系統")
    save_setting("logo_url", logo_url.strip())
    sheet_bust_cache()
    st.session_state.pop("_settings_login_enabled_cache", None)


def get_system_reset_targets() -> tuple[list[str], list[str]]:
    target_tables = [
        "stocktakes",
        "stocktake_lines",
        "purchase_orders",
        "purchase_order_lines",
        "transactions",
    ]
    target_sequence_keys = [
        "stocktakes",
        "stocktake_lines",
        "purchase_orders",
        "purchase_order_lines",
    ]
    return target_tables, target_sequence_keys


def is_system_reset_confirmed(confirm_text: str) -> bool:
    return confirm_text.strip().upper() == "RESET"


def run_system_reset(*, target_tables: list[str], target_sequence_keys: list[str], actor: str):
    for sheet_name in target_tables:
        sheet_clear_keep_header(sheet_name)
    reset_sequence_keys(
        target_keys=target_sequence_keys,
        next_value=1,
        actor=actor,
    )
    sheet_bust_cache()



# ============================================================
# Public API aliases
# ============================================================
read_login_enabled_setting = _read_login_enabled_setting
clear_login_session_state = _clear_login_session_state
is_bypass_mode = _is_bypass_mode
has_locked_system_access = _has_locked_system_access
clear_locked_system_access = _clear_locked_system_access
go_owner_verify = _go_owner_verify
render_locked_system_login_required = _render_locked_system_login_required
worksheet_clear_keep_header = _worksheet_clear_keep_header
reset_sequence_keys = _reset_sequence_keys
load_id_sequences_view = _load_id_sequences_view

__all__ = [
    "clear_locked_system_access",
    "clear_login_session_state",
    "ensure_login_ready",
    "get_login_enabled_status",
    "get_login_toggle_state",
    "get_setting_value",
    "get_settings_dict",
    "get_system_name",
    "go_owner_verify",
    "has_locked_system_access",
    "init_session",
    "initialize_runtime",
    "is_system_reset_confirmed",
    "is_bypass_mode",
    "load_id_sequences_view",
    "get_system_reset_targets",
    "page_owner_verify",
    "read_login_enabled_setting",
    "render_locked_system_login_required",
    "require_locked_system_page",
    "refresh_runtime_sheet_cache",
    "run_system_reset",
    "reset_sequence_keys",
    "save_setting",
    "save_system_appearance",
    "update_login_enabled_setting",
    "worksheet_clear_keep_header",
]
