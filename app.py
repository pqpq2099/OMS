"""
ORIVIA OMS 主程式入口。

你之後如果想知道：
1. 側邊欄怎麼切頁
2. 每個 step 會進到哪個頁面
3. 系統首頁從哪裡開始

優先先看這個檔案。
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from oms_core import (
    apply_global_style,
    append_rows_by_header,
    bust_cache,
    get_header,
    get_spreadsheet,
    read_table,
)

from pages.page_order_entry import (
    page_select_store,
    page_select_vendor,
    page_order_entry,
    page_order_message_detail,
    page_daily_stock_order_record,
)

from pages.page_reports import (
    page_analysis,
    page_cost_debug,
    page_export,
    page_stock_order_compare,
    page_view_history,
)

from pages.page_purchase_settings import page_purchase_settings
from pages.page_user_admin import page_user_admin
from pages.page_store_admin import page_store_admin
from pages.page_login import (
    page_login,
    render_login_sidebar,
    _load_users_df,
    _norm_text,
    _norm_10,
    _sha256,
)
from pages.page_account_settings import page_account_settings

st.set_page_config(page_title="營運管理系統", layout="centered")


# ============================================================
# [A0] 登入開關判斷
# 用途：
# 1. 從 settings 讀取 login_enabled
# 2. 允許 owner/admin 在系統工具頁一鍵開關登入畫面
# 3. 當 login_enabled = 0 時，自動以免登入模式進入系統
# ============================================================
def _read_login_enabled_setting() -> str:
    """從 settings 讀取 login_enabled，預設為 1（啟用登入）。"""
    try:
        settings_df = read_table("settings").copy()
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
        return value if value in {"0", "1"} else "1"

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
    st.session_state["step"] = "owner_verify"
    st.rerun()


def _check_owner_password(account: str, password: str) -> tuple[bool, str]:
    """驗證 owner 帳號密碼。"""
    users_df = _load_users_df()
    if users_df.empty:
        return False, "users 資料表為空，無法驗證。"

    work = users_df.copy()
    work["account_code"] = work["account_code"].apply(_norm_text)
    work["password_hash"] = work["password_hash"].apply(_norm_text)
    work["role_id"] = work["role_id"].apply(lambda x: _norm_text(x).lower())
    work["is_active"] = work["is_active"].apply(_norm_10)

    target = work[
        (work["account_code"] == _norm_text(account))
        & (work["role_id"] == "owner")
        & (work["is_active"] == 1)
    ]

    if target.empty:
        return False, "此帳號不是啟用中的系統擁有者。"

    user_row = target.iloc[0]
    if _norm_text(user_row.get("password_hash")) != _sha256(password):
        return False, "密碼錯誤。"

    st.session_state["owner_gate_verified"] = True
    st.session_state["owner_gate_display_name"] = _norm_text(user_row.get("display_name"))
    st.session_state["owner_gate_user_id"] = _norm_text(user_row.get("user_id"))
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
            st.session_state["step"] = next_step
            st.rerun()

    if st.button("⬅️ 返回", width="stretch", key="back_from_owner_verify"):
        st.session_state["step"] = "select_store"
        st.rerun()


# ============================================================
# 登入檢查
# ============================================================
LOGIN_ENABLED = _read_login_enabled_setting()

if LOGIN_ENABLED == "0":
    _ensure_login_session_when_disabled()
else:
    if "login_user" not in st.session_state:
        page_login()
        st.stop()

    if st.session_state.get("force_change_password", False):
        page_login()
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
        settings_df = read_table("settings")
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


def get_setting_value(setting_key: str, default: str = "") -> str:
    settings_map = get_settings_dict()
    return settings_map.get(setting_key, default)


def get_system_name() -> str:
    default_name = "營運管理系統"
    value = get_setting_value("system_name", default_name)
    return value if str(value).strip() else default_name


def save_setting(setting_key: str, setting_value: str):

    settings_df = read_table("settings").copy()

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

    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet("settings")
    rows = [settings_df.columns.tolist()] + settings_df.fillna("").astype(str).values.tolist()
    ws.clear()
    ws.update(rows)
    bust_cache()


def _worksheet_clear_keep_header(sheet_name: str):
    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    header = get_header(sheet_name)
    ws = sh.worksheet(sheet_name)
    ws.clear()
    ws.update([header])


def _reset_sequence_keys(target_keys: list[str], next_value: int = 1, actor: str = "owner"):
    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet("id_sequences")
    rows = ws.get_all_values()
    if not rows:
        raise ValueError("id_sequences 沒有資料")

    header = [str(c).strip() for c in rows[0]]
    key_i = header.index("key")
    next_i = header.index("next_value")
    updated_at_i = header.index("updated_at") if "updated_at" in header else None
    updated_by_i = header.index("updated_by") if "updated_by" in header else None

    target_key_set = {str(k).strip() for k in target_keys if str(k).strip()}
    found_keys = set()
    now_ts = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    for r, row in enumerate(rows[1:], start=2):
        row_key = str(row[key_i]).strip() if len(row) > key_i else ""
        if row_key not in target_key_set:
            continue

        ws.update_cell(r, next_i + 1, int(next_value))
        if updated_at_i is not None:
            ws.update_cell(r, updated_at_i + 1, now_ts)
        if updated_by_i is not None:
            ws.update_cell(r, updated_by_i + 1, actor)
        found_keys.add(row_key)

    missing_keys = sorted(target_key_set - found_keys)
    if missing_keys:
        raise ValueError(f"id_sequences 找不到 key：{', '.join(missing_keys)}")


def _load_id_sequences_view() -> pd.DataFrame:
    df = read_table("id_sequences").copy()
    if df.empty:
        return df

    cols = [c for c in ["key", "env", "prefix", "width", "next_value", "updated_at", "updated_by"] if c in df.columns]
    if cols:
        df = df[cols].copy()
    return df.reset_index(drop=True)


def page_system_maintenance():
    st.title("🛠️ 系統維護")

    if st.session_state.role != "owner":
        st.error("你沒有權限進入此頁。")
        return

    if not _render_locked_system_login_required("系統維護"):
        return

    st.markdown("### 初始化營運資料")
    st.warning("此功能會清空庫存、叫貨與交易資料，並將對應序號重設回 1。主資料不會刪除。")

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

    with st.expander("查看本次初始化範圍", expanded=False):
        st.markdown("**會清空的資料表**")
        st.code("\n".join(target_tables), language="text")
        st.markdown("**會重設的 id_sequences key**")
        st.code("\n".join(target_sequence_keys), language="text")
        st.markdown("**不會動到的資料**")
        st.code("vendors\nunits\nitems\nprices\nusers\nstores\nbrands\nsettings", language="text")

    confirm_text = st.text_input("請輸入 RESET 才能執行初始化", key="system_reset_confirm")
    can_run = confirm_text.strip().upper() == "RESET"

    if st.button("🗑️ 初始化庫存 / 叫貨 / 序號", width="stretch", type="primary", disabled=not can_run):
        try:
            for sheet_name in target_tables:
                _worksheet_clear_keep_header(sheet_name)

            _reset_sequence_keys(
                target_keys=target_sequence_keys,
                next_value=1,
                actor=st.session_state.get("role", "owner"),
            )

            bust_cache()
            st.success("✅ 初始化完成：庫存、叫貨、交易資料已清空，對應序號已重設。")
            st.rerun()

        except Exception as e:
            st.error(f"❌ 初始化失敗：{e}")

    st.markdown("---")
    st.markdown("### Sequence 檢查")
    seq_df = _load_id_sequences_view()
    if seq_df.empty:
        st.info("目前讀不到 id_sequences 資料")
    else:
        st.dataframe(seq_df, width="stretch", hide_index=True)

    if st.button("⬅️ 返回", width="stretch", key="back_from_system_maintenance"):
        st.session_state.step = "select_store"
        st.rerun()


def page_system_tools():
    st.title("🧰 系統工具")

    if st.session_state.role != "owner":
        st.error("你沒有權限進入此頁。")
        return

    if not _render_locked_system_login_required("系統工具"):
        return

    st.info("這一頁保留給 Owner 放臨時測試、偵錯工具與未來的小型系統輔助功能。")

    st.markdown("### 登入畫面開關")
    current_login_enabled = get_setting_value("login_enabled", "1").strip()
    if current_login_enabled not in {"0", "1"}:
        current_login_enabled = "1"

    bypass_mode = bool(st.session_state.get("login_bypass_mode", False))

    if current_login_enabled == "1":
        st.success("目前狀態：登入畫面啟用中")
        toggle_label = "🔓 一鍵關閉登入畫面"
        next_value = "0"
        toggle_help = "關閉後，系統會略過帳號密碼，直接以免登入模式進入。"
    else:
        st.warning("目前狀態：登入畫面已關閉（免登入模式）")
        toggle_label = "🔐 一鍵開啟登入畫面"
        next_value = "1"
        toggle_help = "開啟後，系統會恢復帳號密碼登入。"

    st.caption(toggle_help)

    if st.button(toggle_label, width="stretch", type="primary", key="toggle_login_enabled"):
        try:
            save_setting("login_enabled", next_value)
            bust_cache()
            _clear_login_session_state()
            st.session_state.step = "select_store"
            st.success("登入畫面設定已更新。")
            st.rerun()
        except Exception as e:
            st.error(f"切換失敗：{e}")

    st.markdown("---")

    if st.button("♻️ 重新整理快取", width="stretch"):
        bust_cache()
        st.success("已清除 read_table 快取。")

    st.markdown("### 目前狀態")
    st.write(f"目前角色：{st.session_state.get('role', '')}")
    st.write(f"目前 step：{st.session_state.get('step', '')}")
    st.write(f"目前分店：{st.session_state.get('store_name', '')}")
    st.write(f"目前廠商：{st.session_state.get('vendor_name', '')}")
    st.write(f"免登入模式：{'是' if bypass_mode else '否'}")

    if st.button("⬅️ 返回", width="stretch", key="back_from_system_tools"):
        st.session_state.step = "select_store"
        st.rerun()


# ============================================================
# [A3] 暫時占位頁
# 用途：
# 某個功能入口先建好，但正式內容還沒完成時，先用這個占位。
# ============================================================
def page_placeholder(title: str, desc: str = "此功能入口已建立，功能尚未接上。"):

    st.title(title)
    st.info(desc)
    st.markdown("---")
    st.caption("目前為占位頁，之後會接正式功能。")



# ============================================================
# [E8] 系統外觀設定頁
# 你之後如果想改：
# 1. 系統名稱
# 2. logo URL
# 3. 主題色
# 4. 時區等系統設定
# 先看這頁。
# ============================================================

def page_appearance_settings():
    st.title("🎨 系統外觀")

    if st.session_state.role not in ["owner", "admin"]:
        st.error("你沒有權限進入此頁。")
        return

    settings_map = get_settings_dict()

    current_system_name = settings_map.get("system_name", "營運管理系統")
    current_logo_url = settings_map.get("logo_url", "")

    st.caption("此頁只調整顯示相關設定，不修改營運邏輯。")

    system_name = st.text_input(
        "系統名稱",
        value=current_system_name,
        key="appearance_system_name",
    )

    logo_url = st.text_input(
        "Logo URL",
        value=current_logo_url,
        key="appearance_logo_url",
    )

    st.markdown("#### 預覽")
    preview_name = system_name.strip() or "營運管理系統"
    st.markdown(f"**目前預覽名稱：** {preview_name}")

    if logo_url.strip():
        try:
            st.image(logo_url.strip(), width=140)
        except Exception:
            st.warning("Logo 預覽失敗，請檢查 URL 是否正確。")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("💾 儲存外觀設定", width="stretch", key="save_appearance_settings"):
            try:
                save_setting("system_name", system_name.strip() or "營運管理系統")
                save_setting("logo_url", logo_url.strip())
                bust_cache()
                st.success("外觀設定已儲存")
                st.rerun()
            except Exception as e:
                st.error(f"儲存失敗：{e}")

    with c2:
        if st.button("⬅️ 返回", width="stretch", key="back_from_appearance_settings"):
            st.session_state.step = "select_store"
            st.rerun()


def page_system_info():
    st.title("ℹ️ 系統資訊")

    if st.session_state.role not in ["owner", "admin"]:
        st.error("你沒有權限進入此頁。")
        return

    settings_map = get_settings_dict()

    display_rows = [
        ("系統名稱", settings_map.get("system_name", "營運管理系統")),
        ("幣別", settings_map.get("currency", "")),
        ("時區", settings_map.get("timezone", "")),
        ("建議叫貨天數", settings_map.get("default_suggestion_days", "")),
        ("歷史天數", settings_map.get("history_days", "")),
        ("Logo URL", settings_map.get("logo_url", "")),
    ]

    st.caption("此頁以查看系統目前設定為主，不直接修改營運邏輯參數。")
    info_df = pd.DataFrame(display_rows, columns=["項目", "目前值"])
    st.dataframe(info_df, width="stretch", hide_index=True)

    if st.button("⬅️ 返回", width="stretch", key="back_from_system_info"):
        st.session_state.step = "select_store"
        st.rerun()


            
# ============================================================
# Sidebar
# ============================================================

# ============================================================
# [S1] Sidebar 側邊欄
# 你最常改的地方之一：
# 1. 側邊欄分組順序
# 2. 哪些按鈕顯示給哪些角色
# 3. 每個按鈕按下後要切到哪個 step
# ============================================================
def render_sidebar():
    role = st.session_state.get("login_role_id", "")
    system_name = get_system_name()
    logo_url = get_setting_value("logo_url", "").strip()

    with st.sidebar:
        # ====================================================
        # 系統 Logo
        # ====================================================
        if logo_url:
            try:
                st.image(logo_url, width=140)
            except Exception:
                st.caption("Logo 載入失敗")

        # ====================================================
        # 系統名稱
        # ====================================================
        st.markdown(f"## {system_name}")

        # ====================================================
        # 作業
        # ====================================================
        st.markdown("### 作業")

        if st.button("🏠 選擇分店", width="stretch", key="sb_select_store"):
            st.session_state.step = "select_store"
            st.rerun()

        if st.button("🧾 叫貨明細", width="stretch", key="sb_order_message_detail"):
            st.session_state.step = "order_message_detail"
            st.rerun()

        if st.button("📄 庫存＋叫貨對照表", width="stretch", key="sb_stock_order_compare"):
            st.session_state.step = "stock_order_compare"
            st.rerun()

        st.markdown("---")

        # ====================================================
        # 分析
        # ====================================================
        st.markdown("### 分析")

        if st.button("📊 進銷存分析", width="stretch", key="sb_analysis"):
            st.session_state.step = "analysis"
            st.rerun()

        if st.button("📦 歷史叫貨紀錄", width="stretch", key="sb_view_history"):
            st.session_state.step = "view_history"
            st.rerun()
        
        if st.button("📤 資料匯出", width="stretch", key="sb_export"):
            st.session_state.step = "export"
            st.rerun()

        st.markdown("---")

        # ====================================================
        # 資料管理
        # ====================================================
        st.markdown("### 資料管理")

        if role in ["owner", "admin"]:
            if st.button("🛒 採購設定", width="stretch", key="sb_purchase_settings"):
                st.session_state.step = "purchase_settings"
                st.rerun()
                
        if role in ["owner", "admin"]:
            if st.button("🧮 成本檢查", width="stretch", key="sb_cost_debug"):
                st.session_state.step = "cost_debug"
                st.rerun()

            if st.button("🏬 分店管理", width="stretch", key="sb_store_admin"):
                st.session_state.step = "store_admin"
                st.rerun()

        st.markdown("---")

        # ====================================================
        # 使用者與權限
        # ====================================================
        st.markdown("### 使用者與權限")

        if role in ["owner", "admin"]:
            if st.button("👥 使用者管理", width="stretch", key="sb_user_admin"):
                st.session_state.step = "user_admin"
                st.rerun()

        if st.button("🙍 個人帳號管理", width="stretch", key="sb_account_settings"):
            st.session_state.step = "account_settings"
            st.rerun()

        st.markdown("---")

        # ====================================================
        # 登入資訊
        # 放在側邊欄最底部
        # ====================================================
        render_login_sidebar()
        # ====================================================
        # 系統
        # 這一區放系統層級功能
        # ====================================================
        if role in ["owner", "admin"]:
            st.markdown("### 系統")

            if st.button("🎨 系統外觀", width="stretch", key="sb_appearance_settings"):
                st.session_state.step = "appearance_settings"
                st.rerun()
            
            if st.button("ℹ️ 系統資訊", width="stretch", key="sb_system_info"):
                st.session_state.step = "system_info"
                st.rerun()


            if role == "owner":
                if _is_bypass_mode():
                    if _has_locked_system_access():
                        verified_name = st.session_state.get("owner_gate_display_name", "")
                        if verified_name:
                            st.caption(f"已驗證：{verified_name}")

                        if st.button("🛠 系統維護", width="stretch", key="sb_system_maintenance"):
                            st.session_state.step = "system_maintenance"
                            st.rerun()

                        if st.button("🧰 系統工具", width="stretch", key="sb_system_tools"):
                            st.session_state.step = "system_tools"
                            st.rerun()

                        if st.button("🔓 登出系統管理", width="stretch", key="sb_owner_gate_logout"):
                            _clear_locked_system_access()
                            st.session_state.step = "select_store"
                            st.rerun()
                    else:
                        if st.button("🔐 系統管理登入", width="stretch", key="sb_owner_verify"):
                            _go_owner_verify("system_tools")
                else:
                    if st.button("🛠 系統維護", width="stretch", key="sb_system_maintenance"):
                        st.session_state.step = "system_maintenance"
                        st.rerun()

                    if st.button("🧰 系統工具", width="stretch", key="sb_system_tools"):
                        st.session_state.step = "system_tools"
                        st.rerun()

# ============================================================
# Router
# ============================================================

# ============================================================
# [S2] Router 路由中心
# 這裡就是「step 對應哪個頁面函式」的總開關。
# 之後只要遇到：按鈕按了跑錯頁 / 找不到頁 / 新頁面接不上，
# 第一個先檢查這裡。
# ============================================================
def router():
    step = st.session_state.step

    # ---------------------------
    # 正式已完成頁面
    # ---------------------------
    if step == "select_store":
        page_select_store()

    elif step == "select_vendor":
        page_select_vendor()

    elif step == "order_entry":
        page_order_entry()

    elif step == "daily_stock_order_record":
        page_daily_stock_order_record()
    
    elif step == "order_message_detail":
        page_order_message_detail()
    
    elif step == "export":
        page_export()

    elif step == "stock_order_compare":
        page_stock_order_compare()

    elif step == "analysis":
        page_analysis()

    elif step == "view_history":
        page_view_history()

    elif step == "cost_debug":
        page_cost_debug()

    elif step == "appearance_settings":
        page_appearance_settings()
    
    elif step == "password_tool":
        from pages.page_password_tool import page_password_tool
        page_password_tool()
    
    elif step == "system_info":
        page_system_info()

    elif step == "owner_verify":
        page_owner_verify()

    # ---------------------------
    # 入口先建立，功能待接
    # ---------------------------
    elif step == "purchase_history":
        page_placeholder("🧾 歷史叫貨紀錄")

    elif step == "data_export":
        page_placeholder("📤 資料匯出")

    elif step == "user_admin":
        page_user_admin()

    elif step == "account_settings":
        page_account_settings()

    elif step == "purchase_settings":
        page_purchase_settings()

    elif step == "store_admin":
        page_store_admin()
    
    elif step == "system_maintenance":
        page_system_maintenance()

    elif step == "system_tools":
        page_system_tools()

    else:
        page_select_store()


# ============================================================
# Main
# ============================================================



# ============================================================
# [S3] main 主流程入口
# 程式啟動後，會由這裡開始：
# 1. 套用樣式
# 2. 初始化 session
# 3. 畫 sidebar
# 4. 依 step 進 router
# ============================================================
def main():
    apply_global_style()
    init_session()
    render_sidebar()
    router()


if __name__ == "__main__":
    main()





