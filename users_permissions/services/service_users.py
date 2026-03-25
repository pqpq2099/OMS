# ============================================================
# ORIVIA OMS
# 檔案：services/service_users.py
# 說明：使用者管理服務層
# 功能：處理帳號、角色、分店範圍與權限相關邏輯。
# 注意：升遷、停用、角色調整建議統一走這層。
# ============================================================

from __future__ import annotations

from datetime import datetime
import hashlib

import pandas as pd

from shared.services.service_audit import audit_log
from shared.services.service_id import allocate_user_id
from shared.services.service_sheet import sheet_append, sheet_bust_cache, sheet_get_header, sheet_read, sheet_update


class UserServiceError(ValueError):
    """使用者／帳號管理可預期錯誤。"""


_USER_COLUMNS = [
    "user_id",
    "account_code",
    "email",
    "display_name",
    "password_hash",
    "must_change_password",
    "role_id",
    "store_scope",
    "is_active",
    "last_login_at",
    "created_at",
    "updated_at",
    "updated_by",
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


def sha256_password(password: str) -> str:
    return hashlib.sha256((password or "").encode("utf-8")).hexdigest()


def norm_10(value) -> int:
    text = norm_text(value).lower()
    return 1 if text in {"1", "true", "yes", "y"} else 0


def ensure_user_columns(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    for col in _USER_COLUMNS:
        if col not in work.columns:
            work[col] = ""
    return work


def load_users_df() -> pd.DataFrame:
    df = sheet_read("users").copy()
    if df.empty:
        return pd.DataFrame(columns=_USER_COLUMNS)
    return ensure_user_columns(df)


def role_label(role_id: str) -> str:
    mapping = {
        "owner": "負責人",
        "admin": "管理員",
        "store_manager": "店長",
        "leader": "組長",
        "staff": "一般員工",
        "employee": "一般員工",
        "test_admin": "測試管理員",
        "test_store_manager": "測試店長",
    }
    rid = norm_text(role_id).lower()
    return mapping.get(rid, rid or "-")


def build_account_info_df(user_row: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"欄位": "帳號", "內容": norm_text(user_row.get("account_code")) or "-"},
            {"欄位": "姓名", "內容": norm_text(user_row.get("display_name")) or "-"},
            {"欄位": "角色", "內容": role_label(user_row.get("role_id"))},
            {"欄位": "分店範圍", "內容": norm_text(user_row.get("store_scope")) or "-"},
            {"欄位": "Email", "內容": norm_text(user_row.get("email")) or "-"},
        ]
    )


def _normalize_login_df(users_df: pd.DataFrame | None = None) -> pd.DataFrame:
    work = load_users_df() if users_df is None else ensure_user_columns(users_df)
    if work.empty:
        return work
    work = work.copy()
    work["user_id"] = work["user_id"].apply(norm_text)
    work["account_code"] = work["account_code"].apply(norm_text)
    work["display_name"] = work["display_name"].apply(norm_text)
    work["password_hash"] = work["password_hash"].apply(norm_text)
    work["role_id"] = work["role_id"].apply(lambda x: norm_text(x).lower())
    work["store_scope"] = work["store_scope"].apply(norm_text)
    work["is_active"] = work["is_active"].apply(norm_10)
    work["must_change_password"] = work["must_change_password"].apply(norm_10)
    return work


def get_user_row(user_id: str) -> pd.Series:
    target_user_id = norm_text(user_id)
    if not target_user_id:
        raise UserServiceError("缺少 user_id")

    work = _normalize_login_df()
    if work.empty:
        raise UserServiceError("users 表讀取失敗")

    hit = work[work["user_id"] == target_user_id].copy()
    if hit.empty:
        raise UserServiceError("找不到目前登入者資料")
    return hit.iloc[0].copy()


def build_login_session_payload(user_row: pd.Series) -> dict[str, object]:
    return {
        "login_user": norm_text(user_row.get("user_id")),
        "login_account_code": norm_text(user_row.get("account_code")),
        "login_display_name": norm_text(user_row.get("display_name")),
        "login_role_id": norm_text(user_row.get("role_id")).lower(),
        "login_store_scope": norm_text(user_row.get("store_scope")),
        "force_change_password": norm_10(user_row.get("must_change_password")) == 1,
    }


# ------------------------------------------------------------
# 登入 / owner 初始化 / 強制改密
# ------------------------------------------------------------
def get_owner_first_setup_row() -> pd.Series | None:
    work = _normalize_login_df()
    if work.empty:
        return None
    owner_df = work[(work["role_id"] == "owner") & (work["is_active"] == 1)].copy()
    if owner_df.empty:
        return None
    owner_row = owner_df.iloc[0].copy()
    if norm_text(owner_row.get("password_hash")) != "":
        return None
    return owner_row


def validate_new_password(new_password: str, confirm_password: str):
    if not new_password or not confirm_password:
        raise UserServiceError("請完整輸入密碼與確認密碼。")
    if len(new_password) < 6:
        raise UserServiceError("密碼至少 6 碼。")
    if new_password != confirm_password:
        raise UserServiceError("兩次輸入的密碼不一致。")


def update_user_fields(user_id: str, updates: dict):
    target_user_id = norm_text(user_id)
    if not target_user_id:
        raise UserServiceError("缺少 user_id")
    sheet_update("users", "user_id", target_user_id, updates)
    sheet_bust_cache()


def initialize_owner_password(user_id: str, new_password: str, confirm_password: str):
    owner_row = get_user_row(user_id)
    if norm_text(owner_row.get("role_id")).lower() != "owner":
        raise UserServiceError("只有 owner 可執行首次初始化。")
    if norm_text(owner_row.get("password_hash")) != "":
        raise UserServiceError("此 owner 已完成初始化。")

    validate_new_password(new_password, confirm_password)

    updates = {
        "password_hash": sha256_password(new_password),
        "must_change_password": 0,
        "updated_at": now_ts(),
        "updated_by": norm_text(owner_row.get("user_id")) or "owner_first_setup",
    }
    update_user_fields(norm_text(owner_row.get("user_id")), updates)
    audit_log(
        action="owner_first_setup",
        entity_id=norm_text(owner_row.get("user_id")),
        before={"password_hash": "", "must_change_password": norm_text(owner_row.get("must_change_password"))},
        after=updates,
        note="系統首次初始化 owner 密碼",
    )
    return {"message": "初始化完成，請直接登入。", "user_id": norm_text(owner_row.get("user_id"))}


def authenticate_user(account: str, password: str) -> pd.Series:
    work = _normalize_login_df()
    if work.empty:
        raise UserServiceError("users 資料表為空，無法登入。")

    target = work[(work["account_code"] == norm_text(account)) & (work["is_active"] == 1)].copy()
    if target.empty:
        raise UserServiceError("帳號不存在，或此帳號未啟用。")

    user_row = target.iloc[0].copy()
    if norm_text(user_row.get("password_hash")) != sha256_password(password):
        raise UserServiceError("密碼錯誤。")
    return user_row


def record_login_success(user_id: str):
    target_user_id = norm_text(user_id)
    if not target_user_id:
        return
    timestamp = now_ts()
    update_user_fields(
        target_user_id,
        {
            "last_login_at": timestamp,
            "updated_at": timestamp,
        },
    )


def login_user(account: str, password: str) -> dict[str, object]:
    user_row = authenticate_user(account, password)
    try:
        record_login_success(norm_text(user_row.get("user_id")))
    except Exception:
        pass
    return build_login_session_payload(user_row)


def authenticate_owner(account: str, password: str) -> pd.Series:
    user_row = authenticate_user(account, password)
    if norm_text(user_row.get("role_id")).lower() != "owner":
        raise UserServiceError("此帳號不是啟用中的系統擁有者。")
    return user_row


def force_change_password(user_id: str, new_password: str, confirm_password: str):
    target_user_id = norm_text(user_id)
    if not target_user_id:
        raise UserServiceError("登入狀態遺失，請重新登入。")

    validate_new_password(new_password, confirm_password)
    user_row = get_user_row(target_user_id)

    before = {
        "password_hash": norm_text(user_row.get("password_hash")),
        "must_change_password": norm_text(user_row.get("must_change_password")),
        "updated_at": norm_text(user_row.get("updated_at")),
    }
    updates = {
        "password_hash": sha256_password(new_password),
        "must_change_password": 0,
        "updated_at": now_ts(),
        "updated_by": target_user_id,
    }
    update_user_fields(target_user_id, updates)
    audit_log(
        action="force_change_password",
        entity_id=target_user_id,
        before=before,
        after=updates,
        note="登入後強制修改密碼",
    )
    return {"message": "密碼更新成功。", "user_id": target_user_id}


# ------------------------------------------------------------
# 個人帳號管理
# ------------------------------------------------------------
def validate_self_password_change(user_row: pd.Series, current_password: str, new_password: str, confirm_password: str):
    current_hash = norm_text(user_row.get("password_hash"))

    if not current_password or not new_password or not confirm_password:
        raise UserServiceError("請完整輸入目前密碼、新密碼、確認密碼。")

    if current_hash != sha256_password(current_password):
        raise UserServiceError("目前密碼不正確。")

    if len(new_password) < 6:
        raise UserServiceError("新密碼至少需要 6 碼。")

    if new_password != confirm_password:
        raise UserServiceError("新密碼與確認密碼不一致。")

    if current_password == new_password:
        raise UserServiceError("新密碼不可與目前密碼相同。")


def change_own_password(user_id: str, current_password: str, new_password: str, confirm_password: str):
    target_user_id = norm_text(user_id)
    user_row = get_user_row(target_user_id)
    validate_self_password_change(user_row, current_password, new_password, confirm_password)

    before = {
        "password_hash": norm_text(user_row.get("password_hash")),
        "must_change_password": norm_text(user_row.get("must_change_password")),
        "updated_at": norm_text(user_row.get("updated_at")),
        "updated_by": norm_text(user_row.get("updated_by")),
    }
    updates = {
        "password_hash": sha256_password(new_password),
        "must_change_password": 0,
        "updated_at": now_ts(),
        "updated_by": target_user_id,
    }

    update_user_fields(target_user_id, updates)

    audit_log(
        action="self_change_password",
        entity_id=target_user_id,
        before=before,
        after=updates,
        note="使用者於個人帳號管理頁自行修改密碼",
    )

    return {"message": "✅ 密碼已更新", "user_id": target_user_id}


# ------------------------------------------------------------
# 使用者管理（管理員）
# ------------------------------------------------------------
def create_user_account(data: dict, actor_user_id: str = "") -> str:
    account_code = norm_text(data.get("account_code"))
    display_name = norm_text(data.get("display_name"))
    role_id = norm_text(data.get("role_id")).lower()
    store_scope = norm_text(data.get("store_scope"))
    if not account_code:
        raise UserServiceError("請輸入帳號")
    if not display_name:
        raise UserServiceError("請輸入姓名")
    if not role_id:
        raise UserServiceError("請選擇角色")

    users_df = _normalize_login_df()
    if not users_df.empty:
        dup = users_df[users_df["account_code"].str.lower() == account_code.lower()]
        if not dup.empty:
            raise UserServiceError("帳號已存在")

    new_user_id = allocate_user_id()
    now_value = now_ts()
    actor = norm_text(actor_user_id)
    new_row = {
        "user_id": new_user_id,
        "account_code": account_code,
        "email": "",
        "display_name": display_name,
        "password_hash": sha256_password("123456"),
        "must_change_password": 1,
        "role_id": role_id,
        "store_scope": store_scope,
        "is_active": 1,
        "last_login_at": "",
        "created_at": now_value,
        "created_by": actor,
        "updated_at": now_value,
        "updated_by": actor,
    }
    header = sheet_get_header("users")
    sheet_append("users", header, [new_row])
    sheet_bust_cache()
    audit_log(
        action="create_user",
        entity_id=new_user_id,
        before=None,
        after={
            "account_code": account_code,
            "display_name": display_name,
            "role_id": role_id,
            "store_scope": store_scope,
            "is_active": 1,
        },
        note="Create new user",
    )
    return new_user_id


def update_user_profile(
    user_id: str,
    updates: dict,
    *,
    before: dict | None = None,
    after: dict | None = None,
    action: str = "update_user",
    note: str = "Update user profile",
    actor_user_id: str = "",
):
    target_user_id = norm_text(user_id)
    if not target_user_id:
        raise UserServiceError("缺少 user_id")
    actor = norm_text(actor_user_id)
    final_updates = dict(updates or {})
    final_updates.setdefault("updated_at", now_ts())
    if actor:
        final_updates.setdefault("updated_by", actor)
    update_user_fields(target_user_id, final_updates)
    audit_log(action=action, entity_id=target_user_id, before=before or {}, after=after or final_updates, note=note)
    return target_user_id


def reset_user_password_admin(user_id: str, target_row: dict, actor_user_id: str = ""):
    target_user_id = norm_text(user_id)
    before = {
        "user_id": target_user_id,
        "account_code": norm_text(target_row.get("account_code")),
        "must_change_password": norm_text(target_row.get("must_change_password")),
    }
    return update_user_profile(
        target_user_id,
        {
            "password_hash": sha256_password("123456"),
            "must_change_password": 1,
        },
        before=before,
        after={"must_change_password": 1},
        action="reset_password",
        note="Reset password to default 123456",
        actor_user_id=actor_user_id,
    )


def toggle_user_active_admin(user_id: str, target_row: dict, target_next_active: int, actor_user_id: str = ""):
    target_user_id = norm_text(user_id)
    before = {
        "user_id": target_user_id,
        "is_active": int(target_row.get("is_active", 1)),
    }
    return update_user_profile(
        target_user_id,
        {"is_active": int(target_next_active)},
        before=before,
        after={"is_active": int(target_next_active)},
        action="toggle_user_active",
        note="Adjust user active status",
        actor_user_id=actor_user_id,
    )


__all__ = [
    "UserServiceError",
    "authenticate_owner",
    "authenticate_user",
    "build_account_info_df",
    "build_login_session_payload",
    "change_own_password",
    "force_change_password",
    "get_owner_first_setup_row",
    "get_user_row",
    "initialize_owner_password",
    "load_users_df",
    "login_user",
    "norm_text",
    "norm_10",
    "record_login_success",
    "role_label",
    "sha256_password",
    "update_user_fields",
    "now_ts",
    "create_user_account",
    "update_user_profile",
    "reset_user_password_admin",
    "toggle_user_active_admin",
]
