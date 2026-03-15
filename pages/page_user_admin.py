# ============================================================
# ORIVIA OMS
# 檔案：pages/page_user_admin.py
# 說明：使用者與權限管理頁
# 功能：使用者列表、帳號編輯、分店權限、升遷與角色調整、角色權限表。
# 注意：這是權限管理核心頁，異動需同步寫入 audit_logs。
# ============================================================

"""
頁面模組：使用者與權限管理

功能：
1. 顯示使用者列表
2. 新增 / 編輯使用者
3. 店長 / 組長分店管理
4. 升遷與角色調整
5. 顯示角色權限表

資料來源：
Google Sheet
- users
- roles
- stores
- audit_logs

設計原則：
1. 沿用目前 OMS 既有架構
2. 統一使用 oms_core 的 read_table / append_rows_by_header / get_header / allocate_ids
3. 此頁只做帳號與角色管理，不負責登入驗證
4. 權限控制以 role + store_scope + is_active 為主
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json

import pandas as pd
import streamlit as st

from oms_core import (
    read_table,
    append_rows_by_header,
    get_header,
    allocate_ids,
    get_spreadsheet,
    bust_cache,
)


# ============================================================
# [U0] 基本工具
# ============================================================
def _hash_password(password: str) -> str:
    """把明碼轉成 SHA256，和目前登入頁一致。"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _now_ts() -> str:
    """回傳目前時間字串。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _norm_text(value) -> str:
    """安全轉字串。"""
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


# 角色中文顯示
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


PROMOTION_ROLE_ORDER = [
    "staff",
    "leader",
    "store_manager",
    "admin",
]


# ============================================================
# [U1] 欄位安全輔助
# ============================================================
def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """確保 DataFrame 至少包含指定欄位，不足時自動補空字串欄位。"""
    work = df.copy()
    for col in columns:
        if col not in work.columns:
            work[col] = ""
    return work


def _pick_first_existing_column(df: pd.DataFrame, candidates: list[str], fallback: str) -> str:
    """從候選欄位中挑第一個存在的欄位。"""
    for col in candidates:
        if col in df.columns:
            return col
    return fallback


def _safe_active_series(df: pd.DataFrame, col: str = "is_active") -> pd.Series:
    """將啟用欄位統一轉成 1/0，兼容 1 / 1.0 / TRUE / true / yes。"""
    if col not in df.columns:
        return pd.Series([1] * len(df), index=df.index)

    raw = df[col].copy()
    raw_str = raw.astype(str).str.strip().str.lower()
    true_mask = raw_str.isin(["1", "1.0", "true", "yes", "y"])
    false_mask = raw_str.isin(["0", "0.0", "false", "no", "n"])

    result = pd.Series(1, index=df.index, dtype="int64")
    result.loc[false_mask] = 0
    result.loc[true_mask] = 1

    numeric_mask = ~(true_mask | false_mask)
    if numeric_mask.any():
        numeric_values = pd.to_numeric(raw[numeric_mask], errors="coerce")
        result.loc[numeric_mask] = numeric_values.fillna(1).astype(int)

    return result


def _write_back_users_df(users_df: pd.DataFrame):
    """依 users 原始 header，將整張 users 表寫回 Google Sheet。"""
    users_header = get_header("users")
    work = users_df.copy()

    for col in users_header:
        if col not in work.columns:
            work[col] = ""

    work = work[users_header].copy()
    rows = [users_header] + work.fillna("").astype(str).values.tolist()

    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet("users")
    ws.clear()
    ws.update(rows)
    bust_cache()


def _load_users_df() -> pd.DataFrame:
    """讀取 users 並補齊欄位。"""
    users_df = read_table("users").copy()

    if users_df.empty:
        users_df = pd.DataFrame(columns=[
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
            "created_by",
            "updated_at",
            "updated_by",
        ])

    users_df = _ensure_columns(
        users_df,
        [
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
            "created_by",
            "updated_at",
            "updated_by",
        ],
    )

    users_df["account_code"] = users_df["account_code"].astype(str).str.strip()
    users_df["display_name"] = users_df["display_name"].astype(str).str.strip()
    users_df["role_id"] = users_df["role_id"].astype(str).str.strip().str.lower()
    users_df["store_scope"] = users_df["store_scope"].astype(str).str.strip()
    users_df["is_active"] = _safe_active_series(users_df)
    return users_df


def _update_user_fields_by_user_id(user_id: str, updates: dict):
    """以 user_id 為唯一鍵，直接更新 users 表指定欄位。"""
    users_df = _load_users_df()
    if users_df.empty:
        raise ValueError("users 表沒有資料")

    mask = users_df["user_id"].astype(str).str.strip() == str(user_id).strip()
    if not mask.any():
        raise ValueError(f"找不到 user_id：{user_id}")

    for field, value in updates.items():
        if field not in users_df.columns:
            users_df[field] = ""
        users_df.loc[mask, field] = value

    _write_back_users_df(users_df)


def _count_active_store_managers(users_df: pd.DataFrame, store_scope: str, exclude_user_id: str = "") -> int:
    """計算某分店目前啟用中的店長人數。"""
    if users_df.empty:
        return 0

    work = users_df.copy()
    work = _ensure_columns(work, ["user_id", "role_id", "store_scope", "is_active"])
    work["role_id"] = work["role_id"].astype(str).str.strip().str.lower()
    work["store_scope"] = work["store_scope"].astype(str).str.strip()
    work["user_id"] = work["user_id"].astype(str).str.strip()
    work["is_active"] = _safe_active_series(work)

    target_roles = ["store_manager", "test_store_manager"]
    mask = (
        work["role_id"].isin(target_roles)
        & (work["store_scope"] == str(store_scope).strip())
        & (work["is_active"] == 1)
    )
    if exclude_user_id:
        mask = mask & (work["user_id"] != str(exclude_user_id).strip())
    return int(mask.sum())


def _append_audit_log(action: str, entity_id: str, before: dict | None, after: dict | None, note: str = ""):
    """寫入 audit_logs。若失敗則靜默略過，不影響主要操作。"""
    try:
        audit_id = ""
        try:
            audit_id = allocate_ids({"audit_logs": 1})["audit_logs"][0]
        except Exception:
            audit_id = f"AUDIT_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        row = {
            "audit_id": audit_id,
            "ts": _now_ts(),
            "user_id": st.session_state.get("login_user", ""),
            "action": action,
            "table_name": "users",
            "entity_id": entity_id,
            "before_json": json.dumps(before or {}, ensure_ascii=False),
            "after_json": json.dumps(after or {}, ensure_ascii=False),
            "note": note,
        }
        header = get_header("audit_logs")
        append_rows_by_header("audit_logs", header, [row])
    except Exception:
        pass


def _build_store_maps(stores_df: pd.DataFrame) -> tuple[dict[str, str], dict[str, str]]:
    """建立分店顯示與反查字典。"""
    active_stores_df = stores_df.copy()
    active_stores_df["is_active"] = _safe_active_series(active_stores_df)
    active_stores_df = active_stores_df[active_stores_df["is_active"] == 1].copy()

    store_id_to_name = {"ALL": "全部分店"}
    store_name_to_id = {"全部分店": "ALL"}

    for _, row in active_stores_df.iterrows():
        store_id = _norm_text(row.get("store_id"))
        store_name = _norm_text(row.get("store_name_zh")) or _norm_text(row.get("store_name")) or store_id
        if not store_id:
            continue
        store_id_to_name[store_id] = store_name
        store_name_to_id[store_name] = store_id

    return store_id_to_name, store_name_to_id


def _build_role_maps(roles_df: pd.DataFrame, login_role_id: str) -> tuple[dict[str, str], dict[str, str]]:
    """建立角色顯示與反查字典。"""
    active_roles_df = roles_df.copy()
    active_roles_df["is_active"] = _safe_active_series(active_roles_df)
    active_roles_df = active_roles_df[active_roles_df["is_active"] == 1].copy()

    role_id_to_name: dict[str, str] = {}
    role_name_to_id: dict[str, str] = {}

    for _, row in active_roles_df.iterrows():
        role_id = _norm_text(row.get("role_id")).lower()
        role_name = _norm_text(row.get("role_name_zh")) or _norm_text(row.get("role_name")) or ROLE_LABELS.get(role_id, role_id)
        if not role_id:
            continue
        if role_id == "owner":
            continue
        role_id_to_name[role_id] = role_name
        role_name_to_id[role_name] = role_id

    if not role_id_to_name:
        base_roles = {
            "admin": "管理員",
            "store_manager": "店長",
            "leader": "組長",
            "staff": "一般員工",
            "test_admin": "測試管理員",
            "test_store_manager": "測試店長",
            "test_leader": "測試組長",
        }
        role_id_to_name.update(base_roles)
        role_name_to_id.update({v: k for k, v in base_roles.items()})

    if login_role_id != "owner":
        for blocked_role in ["admin", "test_admin"]:
            role_name = role_id_to_name.pop(blocked_role, None)
            if role_name:
                role_name_to_id.pop(role_name, None)

    return role_id_to_name, role_name_to_id


def _user_display_label(row: pd.Series, store_id_to_name: dict[str, str]) -> str:
    """產生使用者選單顯示文字。"""
    name = _norm_text(row.get("display_name")) or _norm_text(row.get("account_code"))
    account = _norm_text(row.get("account_code"))
    role_id = _norm_text(row.get("role_id")).lower()
    role_name = ROLE_LABELS.get(role_id, role_id)
    store_scope = _norm_text(row.get("store_scope"))
    store_name = store_id_to_name.get(store_scope, store_scope or "未設定")
    return f"{name}（{account} / {role_name} / {store_name}）"


def _build_users_view(users_df: pd.DataFrame, roles_df: pd.DataFrame, stores_df: pd.DataFrame) -> pd.DataFrame:
    """建立顯示用 users_view。"""
    role_display_col = _pick_first_existing_column(
        roles_df,
        ["role_name_zh", "role_name"],
        "role_id",
    )

    role_map = roles_df[["role_id", role_display_col]].copy()
    role_map = role_map.rename(columns={role_display_col: "role_display"})
    role_map["role_id"] = role_map["role_id"].astype(str).str.strip().str.lower()

    store_label_col = _pick_first_existing_column(
        stores_df,
        ["store_name_zh", "store_name"],
        "store_id",
    )

    store_map_id = stores_df[["store_id", store_label_col]].copy()
    store_map_id = store_map_id.rename(columns={
        "store_id": "store_scope",
        store_label_col: "store_display_by_id",
    })

    store_map_code = stores_df[["store_code", store_label_col]].copy()
    store_map_code = store_map_code.rename(columns={
        "store_code": "store_scope",
        store_label_col: "store_display_by_code",
    })

    users_view = users_df.copy()
    users_view = users_view.merge(role_map, on="role_id", how="left")
    users_view = users_view.merge(store_map_id, on="store_scope", how="left")
    users_view = users_view.merge(store_map_code, on="store_scope", how="left")

    users_view["role_display"] = users_view["role_display"].fillna(
        users_view["role_id"].map(ROLE_LABELS)
    )
    users_view["role_display"] = users_view["role_display"].fillna(users_view["role_id"])

    users_view["store_display"] = users_view["store_display_by_id"].fillna(users_view["store_display_by_code"])
    users_view.loc[users_view["store_scope"] == "ALL", "store_display"] = "全部分店"
    users_view["store_display"] = users_view["store_display"].fillna("未設定")
    users_view["status_display"] = users_view["is_active"].map({1: "啟用", 0: "停用"}).fillna("啟用")
    return users_view


# ============================================================
# [U2] 使用者權限主頁
# ============================================================
def page_user_admin():
    st.title("👥 使用者權限")

    login_role_id = str(st.session_state.get("login_role_id", "")).strip().lower()
    if login_role_id not in ["owner", "admin"]:
        st.error("你沒有權限進入此頁。")
        return

    users_df = _load_users_df()
    roles_df = _ensure_columns(read_table("roles"), ["role_id", "role_name", "role_name_zh", "is_active"])
    stores_df = _ensure_columns(read_table("stores"), ["store_id", "store_code", "store_name", "store_name_zh", "is_active"])

    # 依既有穩定規則：Owner 不顯示在使用者清單與重設清單中
    managed_users_df = users_df[users_df["role_id"] != "owner"].copy().reset_index(drop=True)
    users_view = _build_users_view(managed_users_df, roles_df, stores_df)

    store_id_to_name, store_name_to_id = _build_store_maps(stores_df)
    role_id_to_name, role_name_to_id = _build_role_maps(roles_df, login_role_id)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "使用者列表",
        "帳號編輯",
        "分店權限",
        "升遷與角色調整",
        "角色權限表",
    ])

    # ========================================================
    # TAB 1 使用者列表
    # ========================================================
    with tab1:
        st.subheader("使用者列表")

        if users_view.empty:
            st.info("目前尚無使用者資料")
        else:
            show_df = users_view[[
                "account_code",
                "display_name",
                "role_display",
                "store_display",
                "status_display",
                "last_login_at",
            ]].copy()
            show_df.columns = ["帳號", "名稱", "角色", "分店", "狀態", "最後登入"]
            st.dataframe(show_df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("快速管理")

        managed_target_df = users_view.sort_values(["display_name", "account_code"]).copy()
        if managed_target_df.empty:
            st.info("目前沒有可管理的使用者")
        else:
            user_option_map = {
                _user_display_label(row, store_id_to_name): row["user_id"]
                for _, row in managed_target_df.iterrows()
            }
            user_labels = list(user_option_map.keys())
            selected_user_label = st.selectbox("選擇使用者", user_labels, key="ua_quick_selected_user")
            selected_user_id = user_option_map.get(selected_user_label, "")

            target_row = managed_target_df[managed_target_df["user_id"] == selected_user_id].iloc[0]
            c1, c2, c3 = st.columns(3)

            with c1:
                if st.button("重設密碼為 123456", use_container_width=True, key="btn_reset_password"):
                    now_ts = _now_ts()
                    before = {
                        "user_id": selected_user_id,
                        "account_code": _norm_text(target_row.get("account_code")),
                        "must_change_password": _norm_text(target_row.get("must_change_password")),
                    }
                    try:
                        _update_user_fields_by_user_id(
                            selected_user_id,
                            {
                                "password_hash": _hash_password("123456"),
                                "must_change_password": 1,
                                "updated_at": now_ts,
                                "updated_by": st.session_state.get("login_user", ""),
                            },
                        )
                        _append_audit_log(
                            action="reset_password",
                            entity_id=selected_user_id,
                            before=before,
                            after={"must_change_password": 1},
                            note="使用者密碼已由管理者重設為預設密碼",
                        )
                        st.success("已重設密碼為 123456，且下次登入需強制修改。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"重設失敗：{e}")

            with c2:
                target_next_active = 0 if int(target_row.get("is_active", 1)) == 1 else 1
                target_label = "停用帳號" if target_next_active == 0 else "啟用帳號"
                if st.button(target_label, use_container_width=True, key="btn_toggle_user_active"):
                    before = {
                        "user_id": selected_user_id,
                        "is_active": int(target_row.get("is_active", 1)),
                    }
                    try:
                        _update_user_fields_by_user_id(
                            selected_user_id,
                            {
                                "is_active": target_next_active,
                                "updated_at": _now_ts(),
                                "updated_by": st.session_state.get("login_user", ""),
                            },
                        )
                        _append_audit_log(
                            action="toggle_user_active",
                            entity_id=selected_user_id,
                            before=before,
                            after={"is_active": target_next_active},
                            note="使用者啟用狀態已調整",
                        )
                        st.success("帳號狀態已更新。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"更新失敗：{e}")

            with c3:
                st.caption("目前狀態")
                st.write(f"角色：{_norm_text(target_row.get('role_display'))}")
                st.write(f"分店：{_norm_text(target_row.get('store_display'))}")
                st.write(f"狀態：{_norm_text(target_row.get('status_display'))}")

    # ========================================================
    # TAB 2 帳號編輯
    # ========================================================
    with tab2:
        st.subheader("新增使用者")

        create_users_df = users_df.copy()
        role_options = list(role_name_to_id.keys())
        store_options = list(store_name_to_id.keys())

        if not role_options:
            st.warning("目前 roles 表沒有可用角色，無法新增使用者。")
        else:
            with st.form("form_create_user", clear_on_submit=True):
                new_account_code = st.text_input("登入帳號", placeholder="例如：staff01").strip()
                new_display_name = st.text_input("顯示名稱", placeholder="例如：阿辰").strip()
                selected_role_name = st.selectbox("角色", options=role_options, index=0)
                selected_role_id = role_name_to_id[selected_role_name]

                default_store_name = "全部分店" if selected_role_id in ["admin", "test_admin"] else (
                    store_options[1] if len(store_options) > 1 and store_options[0] == "全部分店" else store_options[0]
                )
                default_store_index = store_options.index(default_store_name) if default_store_name in store_options else 0
                selected_store_name = st.selectbox("分店", options=store_options, index=default_store_index)
                selected_store_scope = store_name_to_id[selected_store_name]

                st.caption("預設密碼：123456")
                st.caption("建立後，使用者第一次登入會被要求修改密碼。")
                submitted_create = st.form_submit_button("建立使用者", use_container_width=True)

            if submitted_create:
                if not new_account_code:
                    st.error("請輸入帳號。")
                elif not new_display_name:
                    st.error("請輸入名稱。")
                else:
                    work_users = create_users_df.copy()
                    work_users["account_code"] = work_users["account_code"].astype(str).str.strip().str.lower()
                    account_exists = new_account_code.strip().lower() in work_users["account_code"].tolist()

                    if account_exists:
                        st.error("此帳號已存在，請改用其他帳號。")
                    elif selected_role_id in ["store_manager", "leader", "test_store_manager", "test_leader", "staff"] and selected_store_scope == "ALL":
                        st.error("此角色必須綁定指定分店，不可使用全部分店。")
                    elif selected_role_id in ["store_manager", "test_store_manager"] and _count_active_store_managers(users_df, selected_store_scope) >= 3:
                        st.error("此分店店長已達 3 位上限，請先調整後再建立。")
                    else:
                        try:
                            new_user_id = allocate_ids({"users": 1})["users"][0]
                        except Exception:
                            new_user_id = f"USER_{datetime.now().strftime('%Y%m%d%H%M%S')}"

                        now_ts = _now_ts()
                        new_row = {
                            "user_id": new_user_id,
                            "account_code": new_account_code.strip(),
                            "email": "",
                            "display_name": new_display_name.strip(),
                            "password_hash": _hash_password("123456"),
                            "must_change_password": 1,
                            "role_id": selected_role_id,
                            "store_scope": selected_store_scope,
                            "is_active": 1,
                            "last_login_at": "",
                            "created_at": now_ts,
                            "created_by": st.session_state.get("login_user", ""),
                            "updated_at": now_ts,
                            "updated_by": st.session_state.get("login_user", ""),
                        }

                        try:
                            users_header = get_header("users")
                            append_rows_by_header("users", users_header, [new_row])
                            _append_audit_log(
                                action="create_user",
                                entity_id=new_user_id,
                                before=None,
                                after={
                                    "account_code": new_account_code.strip(),
                                    "display_name": new_display_name.strip(),
                                    "role_id": selected_role_id,
                                    "store_scope": selected_store_scope,
                                },
                                note="建立新使用者",
                            )
                            st.success("建立成功。預設密碼為 123456，第一次登入需修改密碼。")
                            st.rerun()
                        except Exception as e:
                            st.error(f"建立失敗：{e}")

        st.divider()
        st.subheader("編輯既有使用者")

        editable_users_df = users_view.sort_values(["display_name", "account_code"]).copy()
        if editable_users_df.empty:
            st.info("目前沒有可編輯的使用者")
        else:
            edit_user_option_map = {
                _user_display_label(row, store_id_to_name): row["user_id"]
                for _, row in editable_users_df.iterrows()
            }
            edit_user_labels = list(edit_user_option_map.keys())
            selected_edit_label = st.selectbox("選擇要編輯的使用者", edit_user_labels, key="ua_edit_selected_user")
            selected_edit_user_id = edit_user_option_map.get(selected_edit_label, "")
            edit_row = editable_users_df[editable_users_df["user_id"] == selected_edit_user_id].iloc[0]

            edit_role_names = list(role_name_to_id.keys())
            current_role_name = role_id_to_name.get(_norm_text(edit_row.get("role_id")), _norm_text(edit_row.get("role_id")))
            edit_role_index = edit_role_names.index(current_role_name) if current_role_name in edit_role_names else 0

            edit_store_names = list(store_name_to_id.keys())
            current_store_name = store_id_to_name.get(_norm_text(edit_row.get("store_scope")), "未設定")
            if current_store_name not in edit_store_names:
                current_store_name = edit_store_names[0]
            edit_store_index = edit_store_names.index(current_store_name)

            with st.form("form_edit_user"):
                edit_display_name = st.text_input("名稱", value=_norm_text(edit_row.get("display_name")), key="edit_display_name")
                edit_role_name = st.selectbox("角色", edit_role_names, index=edit_role_index, key="edit_role_name")
                edit_store_name = st.selectbox("分店", edit_store_names, index=edit_store_index, key="edit_store_name")
                edit_is_active = st.selectbox(
                    "狀態",
                    options=["啟用", "停用"],
                    index=0 if int(edit_row.get("is_active", 1)) == 1 else 1,
                    key="edit_is_active",
                )
                submitted_edit = st.form_submit_button("儲存使用者設定", use_container_width=True)

            if submitted_edit:
                new_role_id = role_name_to_id[edit_role_name]
                new_store_scope = store_name_to_id[edit_store_name]
                new_is_active = 1 if edit_is_active == "啟用" else 0

                if new_role_id in ["store_manager", "leader", "test_store_manager", "test_leader", "staff"] and new_store_scope == "ALL":
                    st.error("此角色必須綁定指定分店，不可使用全部分店。")
                elif new_role_id in ["store_manager", "test_store_manager"] and _count_active_store_managers(users_df, new_store_scope, exclude_user_id=selected_edit_user_id) >= 3:
                    st.error("此分店店長已達 3 位上限，無法更新。")
                else:
                    before = {
                        "display_name": _norm_text(edit_row.get("display_name")),
                        "role_id": _norm_text(edit_row.get("role_id")),
                        "store_scope": _norm_text(edit_row.get("store_scope")),
                        "is_active": int(edit_row.get("is_active", 1)),
                    }
                    after = {
                        "display_name": edit_display_name.strip(),
                        "role_id": new_role_id,
                        "store_scope": new_store_scope,
                        "is_active": new_is_active,
                    }
                    try:
                        _update_user_fields_by_user_id(
                            selected_edit_user_id,
                            {
                                "display_name": edit_display_name.strip(),
                                "role_id": new_role_id,
                                "store_scope": new_store_scope,
                                "is_active": new_is_active,
                                "updated_at": _now_ts(),
                                "updated_by": st.session_state.get("login_user", ""),
                            },
                        )
                        _append_audit_log(
                            action="update_user",
                            entity_id=selected_edit_user_id,
                            before=before,
                            after=after,
                            note="管理者編輯使用者資料",
                        )
                        st.success("使用者資料已更新。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"更新失敗：{e}")

    # ========================================================
    # TAB 3 分店權限
    # ========================================================
    with tab3:
        st.subheader("分店權限管理")

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("#### 店長管理")
            manager_df = users_view[users_view["role_id"].isin(["store_manager", "test_store_manager"])].copy()
            if manager_df.empty:
                st.info("目前沒有店長資料")
            else:
                show_manager_df = manager_df[["account_code", "display_name", "store_display", "status_display"]].copy()
                show_manager_df.columns = ["店長帳號", "店長名稱", "管理分店", "狀態"]
                st.dataframe(show_manager_df, use_container_width=True, hide_index=True)

                manager_option_map = {
                    _user_display_label(row, store_id_to_name): row["user_id"]
                    for _, row in manager_df.sort_values(["display_name", "account_code"]).iterrows()
                }
                manager_labels = list(manager_option_map.keys())
                selected_manager_label = st.selectbox("選擇店長", manager_labels, key="mgr_user_select")
                selected_manager_user_id = manager_option_map.get(selected_manager_label, "")
                manager_row = manager_df[manager_df["user_id"] == selected_manager_user_id].iloc[0]

                store_names_only = [name for name, sid in store_name_to_id.items() if sid != "ALL"]
                current_manager_store_name = store_id_to_name.get(_norm_text(manager_row.get("store_scope")), store_names_only[0])
                if current_manager_store_name not in store_names_only:
                    current_manager_store_name = store_names_only[0]
                manager_store_idx = store_names_only.index(current_manager_store_name)
                selected_manager_store_name = st.selectbox("改派分店", store_names_only, index=manager_store_idx, key="mgr_store_scope_select")
                new_manager_store_scope = store_name_to_id[selected_manager_store_name]

                if st.button("更新店長分店", use_container_width=True, key="btn_update_manager_scope"):
                    if _count_active_store_managers(users_df, new_manager_store_scope, exclude_user_id=selected_manager_user_id) >= 3:
                        st.error("此分店店長已達 3 位上限，無法再指派。")
                    else:
                        before = {"store_scope": _norm_text(manager_row.get("store_scope"))}
                        after = {"store_scope": new_manager_store_scope}
                        try:
                            _update_user_fields_by_user_id(
                                selected_manager_user_id,
                                {
                                    "store_scope": new_manager_store_scope,
                                    "updated_at": _now_ts(),
                                    "updated_by": st.session_state.get("login_user", ""),
                                },
                            )
                            _append_audit_log(
                                action="reassign_store_manager",
                                entity_id=selected_manager_user_id,
                                before=before,
                                after=after,
                                note="調整店長分店",
                            )
                            st.success("店長分店已更新。")
                            st.rerun()
                        except Exception as e:
                            st.error(f"更新失敗：{e}")

        with c2:
            st.markdown("#### 組長管理")
            leader_df = users_view[users_view["role_id"].isin(["leader", "test_leader"])].copy()
            if leader_df.empty:
                st.info("目前沒有組長資料")
            else:
                show_leader_df = leader_df[["account_code", "display_name", "store_display", "status_display"]].copy()
                show_leader_df.columns = ["組長帳號", "組長名稱", "所屬分店", "狀態"]
                st.dataframe(show_leader_df, use_container_width=True, hide_index=True)

                leader_option_map = {
                    _user_display_label(row, store_id_to_name): row["user_id"]
                    for _, row in leader_df.sort_values(["display_name", "account_code"]).iterrows()
                }
                leader_labels = list(leader_option_map.keys())
                selected_leader_label = st.selectbox("選擇組長", leader_labels, key="leader_user_select")
                selected_leader_user_id = leader_option_map.get(selected_leader_label, "")
                leader_row = leader_df[leader_df["user_id"] == selected_leader_user_id].iloc[0]

                store_names_only = [name for name, sid in store_name_to_id.items() if sid != "ALL"]
                current_leader_store_name = store_id_to_name.get(_norm_text(leader_row.get("store_scope")), store_names_only[0])
                if current_leader_store_name not in store_names_only:
                    current_leader_store_name = store_names_only[0]
                leader_store_idx = store_names_only.index(current_leader_store_name)
                selected_leader_store_name = st.selectbox("改派分店", store_names_only, index=leader_store_idx, key="leader_store_scope_select")
                new_leader_store_scope = store_name_to_id[selected_leader_store_name]

                if st.button("更新組長分店", use_container_width=True, key="btn_update_leader_scope"):
                    before = {"store_scope": _norm_text(leader_row.get("store_scope"))}
                    after = {"store_scope": new_leader_store_scope}
                    try:
                        _update_user_fields_by_user_id(
                            selected_leader_user_id,
                            {
                                "store_scope": new_leader_store_scope,
                                "updated_at": _now_ts(),
                                "updated_by": st.session_state.get("login_user", ""),
                            },
                        )
                        _append_audit_log(
                            action="reassign_leader",
                            entity_id=selected_leader_user_id,
                            before=before,
                            after=after,
                            note="調整組長分店",
                        )
                        st.success("組長分店已更新。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"更新失敗：{e}")

    # ========================================================
    # TAB 4 升遷與角色調整
    # ========================================================
    with tab4:
        st.subheader("升遷與角色調整")
        st.caption("這一區用來做既有使用者的角色調整，並同步留下 audit 記錄。")

        promotion_users_df = users_view[
            users_view["role_id"].isin(["staff", "leader", "store_manager", "admin", "test_leader", "test_store_manager", "test_admin"])
        ].copy()

        if promotion_users_df.empty:
            st.info("目前沒有可調整角色的使用者")
        else:
            promotion_user_option_map = {
                _user_display_label(row, store_id_to_name): row["user_id"]
                for _, row in promotion_users_df.sort_values(["display_name", "account_code"]).iterrows()
            }
            promotion_labels = list(promotion_user_option_map.keys())
            selected_promotion_label = st.selectbox("選擇員工", promotion_labels, key="promotion_target_user")
            selected_promotion_user_id = promotion_user_option_map.get(selected_promotion_label, "")
            promotion_row = promotion_users_df[promotion_users_df["user_id"] == selected_promotion_user_id].iloc[0]

            current_role_id = _norm_text(promotion_row.get("role_id")).lower()
            current_role_name = role_id_to_name.get(current_role_id, ROLE_LABELS.get(current_role_id, current_role_id))
            st.write(f"目前角色：{current_role_name}")

            promotion_role_candidates = list(role_name_to_id.keys())
            current_role_name_for_index = role_id_to_name.get(current_role_id, promotion_role_candidates[0])
            role_index = promotion_role_candidates.index(current_role_name_for_index) if current_role_name_for_index in promotion_role_candidates else 0
            new_role_name = st.selectbox("調整為新角色", promotion_role_candidates, index=role_index, key="promotion_new_role")
            new_role_id = role_name_to_id[new_role_name]

            promotion_store_names = list(store_name_to_id.keys())
            current_store_name = store_id_to_name.get(_norm_text(promotion_row.get("store_scope")), promotion_store_names[0])
            if current_store_name not in promotion_store_names:
                current_store_name = promotion_store_names[0]
            store_idx = promotion_store_names.index(current_store_name)
            new_store_name = st.selectbox("同步調整分店", promotion_store_names, index=store_idx, key="promotion_new_store")
            new_store_scope = store_name_to_id[new_store_name]
            promotion_note = st.text_input("備註", placeholder="例如：升任組長 / 調店 / 權限調整", key="promotion_note")

            promotion_kind = "角色不變"
            if current_role_id in PROMOTION_ROLE_ORDER and new_role_id in PROMOTION_ROLE_ORDER:
                current_idx = PROMOTION_ROLE_ORDER.index(current_role_id)
                new_idx = PROMOTION_ROLE_ORDER.index(new_role_id)
                if new_idx > current_idx:
                    promotion_kind = "升遷"
                elif new_idx < current_idx:
                    promotion_kind = "降階 / 角色下調"

            st.caption(f"本次判定：{promotion_kind}")

            if st.button("送出角色調整", use_container_width=True, key="btn_submit_role_change"):
                if new_role_id in ["store_manager", "leader", "test_store_manager", "test_leader", "staff"] and new_store_scope == "ALL":
                    st.error("此角色必須綁定指定分店，不可使用全部分店。")
                elif new_role_id in ["store_manager", "test_store_manager"] and _count_active_store_managers(users_df, new_store_scope, exclude_user_id=selected_promotion_user_id) >= 3:
                    st.error("此分店店長已達 3 位上限，無法調整。")
                else:
                    before = {
                        "role_id": current_role_id,
                        "store_scope": _norm_text(promotion_row.get("store_scope")),
                        "is_active": int(promotion_row.get("is_active", 1)),
                    }
                    after = {
                        "role_id": new_role_id,
                        "store_scope": new_store_scope,
                        "is_active": int(promotion_row.get("is_active", 1)),
                    }
                    try:
                        _update_user_fields_by_user_id(
                            selected_promotion_user_id,
                            {
                                "role_id": new_role_id,
                                "store_scope": new_store_scope,
                                "updated_at": _now_ts(),
                                "updated_by": st.session_state.get("login_user", ""),
                            },
                        )
                        _append_audit_log(
                            action="role_change",
                            entity_id=selected_promotion_user_id,
                            before=before,
                            after=after,
                            note=promotion_note.strip() or f"{promotion_kind}：{current_role_id} -> {new_role_id}",
                        )
                        st.success("角色調整完成。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"調整失敗：{e}")

    # ========================================================
    # TAB 5 角色權限表
    # ========================================================
    with tab5:
        st.subheader("角色權限表")
        st.caption("此頁以顯示制度為主，讓管理者可快速對照各角色可見功能。")
        permission_df = pd.DataFrame(ROLE_PERMISSION_ROWS)
        st.dataframe(permission_df, use_container_width=True, hide_index=True)

        st.markdown("#### 補充說明")
        st.write("- 權限控制以 role + store_scope + is_active 為主，不使用複雜 ACL。")
        st.write("- 成本檢查僅限 Owner / Admin 可見。")
        st.write("- 店長與組長必須綁定指定分店，不可使用全部分店。")
        st.write("- 每店啟用中的店長上限為 3 位。")
