from __future__ import annotations

import pandas as pd


ROLE_LABELS = {
    "owner": "系統負責人",
    "admin": "管理員",
    "store_manager": "店長",
    "leader": "組長",
    "staff": "一般員工",
    "test_admin": "測試管理員",
    "test_store_manager": "測試店長",
    "test_leader": "測試組長",
}


ROLE_PERMISSION_ROWS = [
    {"角色": "系統負責人", "role_id": "owner", "作業": "可", "分析": "可", "資料管理": "可", "使用者管理": "可", "成本檢查": "可", "系統工具": "可"},
    {"角色": "管理員", "role_id": "admin", "作業": "可", "分析": "可", "資料管理": "可", "使用者管理": "可", "成本檢查": "可", "系統工具": "不可"},
    {"角色": "店長", "role_id": "store_manager", "作業": "自己分店", "分析": "自己分店", "資料管理": "不可", "使用者管理": "不可", "成本檢查": "不可", "系統工具": "不可"},
    {"角色": "組長", "role_id": "leader", "作業": "自己分店", "分析": "必要報表", "資料管理": "不可", "使用者管理": "不可", "成本檢查": "不可", "系統工具": "不可"},
    {"角色": "一般員工", "role_id": "staff", "作業": "基本操作", "分析": "不可", "資料管理": "不可", "使用者管理": "不可", "成本檢查": "不可", "系統工具": "不可"},
]


PROMOTION_ROLE_ORDER = ["staff", "leader", "store_manager", "admin"]


def can_access_user_admin(current_role_id: str) -> bool:
    return str(current_role_id or "").strip().lower() in ["owner", "admin"]


def can_view_user(current_user: dict, target_user: dict) -> bool:
    current_role_id = str(current_user.get("role_id", "")).strip().lower()
    target_role_id = str(target_user.get("role_id", "")).strip().lower()
    if current_role_id == "owner":
        return True
    if current_role_id == "admin":
        return target_role_id != "owner"
    return False


def can_edit_user(current_user: dict, target_user: dict) -> bool:
    return can_view_user(current_user, target_user)


def can_assign_role(current_user: dict, role_id: str) -> bool:
    current_role_id = str(current_user.get("role_id", "")).strip().lower()
    role_id = str(role_id or "").strip().lower()
    if current_role_id == "owner":
        return role_id != "owner"
    if current_role_id == "admin":
        return role_id not in ["owner", "admin", "test_admin"]
    return False


def count_active_store_managers(users_df: pd.DataFrame, store_scope: str, exclude_user_id: str = "") -> int:
    if users_df.empty:
        return 0
    work = users_df.copy()
    if "role_id" not in work.columns:
        return 0
    if "store_scope" not in work.columns:
        work["store_scope"] = ""
    if "user_id" not in work.columns:
        work["user_id"] = ""
    if "is_active" not in work.columns:
        work["is_active"] = 1
    work["role_id"] = work["role_id"].astype(str).str.strip().str.lower()
    work["store_scope"] = work["store_scope"].astype(str).str.strip()
    work["user_id"] = work["user_id"].astype(str).str.strip()
    work["is_active"] = pd.to_numeric(work["is_active"], errors="coerce").fillna(1).astype(int)
    target_roles = ["store_manager", "test_store_manager"]
    mask = (
        work["role_id"].isin(target_roles)
        & (work["store_scope"] == str(store_scope).strip())
        & (work["is_active"] == 1)
    )
    if exclude_user_id:
        mask = mask & (work["user_id"] != str(exclude_user_id).strip())
    return int(mask.sum())


def is_admin_role(role_id: str) -> bool:
    return str(role_id or "").strip().lower() in ["admin", "test_admin"]


def requires_specific_store_scope(role_id: str) -> bool:
    return str(role_id or "").strip().lower() in [
        "store_manager",
        "leader",
        "test_store_manager",
        "test_leader",
        "staff",
    ]


def is_store_manager_role(role_id: str) -> bool:
    return str(role_id or "").strip().lower() in ["store_manager", "test_store_manager"]


def is_leader_role(role_id: str) -> bool:
    return str(role_id or "").strip().lower() in ["leader", "test_leader"]


def is_promotion_target_role(role_id: str) -> bool:
    return str(role_id or "").strip().lower() in [
        "staff",
        "leader",
        "store_manager",
        "admin",
        "test_leader",
        "test_store_manager",
        "test_admin",
    ]
