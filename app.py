from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from oms_core import (
    apply_global_style,
    append_rows_by_header,
    bust_cache,
    get_header,
    read_table,
)

from pages_order import (
    page_order_entry,
    page_order_message_detail,
    page_select_store,
    page_select_vendor,
)

from pages_reports import (
    page_analysis,
    page_cost_debug,
    page_export,
    page_purchase_settings,
    page_view_history,
)
st.set_page_config(page_title="營運管理系統", layout="centered")


# ============================================================
# Session State
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

    # 先用假角色測試，之後再接 users / roles
    if "role" not in st.session_state:
        st.session_state.role = "owner"  # owner / admin / store_manager / leader


# ============================================================
# Settings Helpers
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


def get_system_name() -> str:
    default_name = "營運管理系統"

    try:
        settings_df = read_table("settings")
        if settings_df.empty:
            return default_name

        work = settings_df.copy()
        work.columns = [str(c).strip() for c in work.columns]

        key_col, value_col = _get_settings_key_value_cols(work)
        if not key_col or not value_col:
            return default_name

        target = work[
            work[key_col].astype(str).str.strip().str.lower() == "system_name"
        ]

        if target.empty:
            return default_name

        value = str(target.iloc[0][value_col]).strip()
        return value if value else default_name

    except Exception:
        return default_name


def save_setting(setting_key: str, setting_value: str):

    settings_df = read_table("settings").copy()

    # 如果完全沒有資料
    if settings_df.empty:
        settings_df = pd.DataFrame({
            "key": [setting_key],
            "value": [setting_value],
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

    # ------------------------------------------------
    # 覆寫整張 settings 表
    # ------------------------------------------------
    import gspread
    from google.oauth2.service_account import Credentials
    
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope,
    )
    
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(st.secrets["SHEET_ID"]).worksheet("settings")
    
    rows = [settings_df.columns.tolist()] + settings_df.astype(str).values.tolist()
    
    sheet.clear()
    sheet.update(rows)
    
    bust_cache()


# ============================================================
# Placeholder
# ============================================================
def page_placeholder(title: str, desc: str = "此功能入口已建立，功能尚未接上。"):
    st.title(title)
    st.info(desc)
    st.markdown("---")
    st.caption("目前為占位頁，之後會接正式功能。")


# ============================================================
# Appearance Settings Page
# ============================================================
def page_appearance_settings():
    st.title("🎨 系統外觀")

    if st.session_state.role not in ["owner", "admin"]:
        st.error("你沒有權限進入此頁。")
        return

    current_name = get_system_name()

    st.markdown("### 系統名稱設定")
    st.caption("此設定會影響左側 Sidebar 與瀏覽器分頁名稱。")

    new_name = st.text_input("系統名稱", value=current_name)

    if st.button("💾 儲存系統名稱", use_container_width=True):
        try:
            value = new_name.strip()
            if not value:
                st.warning("系統名稱不可空白。")
                return

            save_setting("system_name", value)
            st.success("✅ 已儲存系統名稱，重新整理後會顯示新名稱。")
            st.rerun()

        except Exception as e:
            st.error(f"❌ 儲存失敗：{e}")

    if st.button("⬅️ 返回", use_container_width=True, key="back_from_appearance"):
        st.session_state.step = "select_store"
        st.rerun()


# ============================================================
# Sidebar
# ============================================================
def render_sidebar():
    role = st.session_state.role
    system_name = get_system_name()

    with st.sidebar:
        st.markdown(f"## {system_name}")

        st.write(f"**目前角色：** {role}")

        if st.session_state.store_name:
            st.write(f"**目前分店：** {st.session_state.store_name}")

        if st.session_state.vendor_name:
            st.write(f"**目前廠商：** {st.session_state.vendor_name}")

        st.markdown("---")

        # ====================================================
        # 作業
        # ====================================================
        st.markdown("### 作業")

        if st.button("🏠 選擇分店", use_container_width=True, key="sb_select_store"):
            st.session_state.step = "select_store"
            st.rerun()

        if st.button("🧾 叫貨明細", use_container_width=True, key="sb_order_message_detail"):
            st.session_state.step = "order_message_detail"
            st.rerun()

        # ============================================================
        # 分析
        # ============================================================
        st.markdown("### 分析")

        if st.button("📊 進銷存分析", use_container_width=True, key="sb_analysis"):
            st.session_state.step = "analysis"
            st.rerun()

        if st.button("📜 進貨分析", use_container_width=True, key="sb_view_history"):
            st.session_state.step = "view_history"
            st.rerun()
            
        # ============================================================
        # 後台管理
        # ============================================================
        st.markdown("### 後台管理")

        if st.button("👥 使用者權限", use_container_width=True, key="sb_user_admin"):
            st.session_state.step = "user_admin"
            st.rerun()

        if st.button("🛒 採購設定", use_container_width=True, key="sb_purchase_settings"):
            st.session_state.step = "purchase_settings"
            st.rerun()

        # ====================================================
        # 系統工具（Owner only）
        # ====================================================
        if role == "owner":
            st.markdown("### 系統工具")

            if st.button("🛠️ 系統維護", use_container_width=True, key="sb_system_tools"):
                st.session_state.step = "system_tools"
                st.rerun()

            if st.button("🧪 開發測試", use_container_width=True, key="sb_dev_test"):
                st.session_state.step = "dev_test"
                st.rerun()


# ============================================================
# Router
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
    
    elif step == "order_message_detail":
        page_order_message_detail()
    
    elif step == "export":
        page_export()

    elif step == "analysis":
        page_analysis()

    elif step == "view_history":
        page_view_history()

    elif step == "cost_debug":
        page_cost_debug()

    elif step == "appearance_settings":
        page_appearance_settings()

    # ---------------------------
    # 入口先建立，功能待接
    # ---------------------------
    elif step == "purchase_history":
        page_placeholder("🧾 歷史叫貨紀錄")

    elif step == "data_export":
        page_placeholder("📤 資料匯出")

    elif step == "user_admin":
        page_placeholder("👥 使用者權限")

    elif step == "purchase_settings":
        page_purchase_settings()

    elif step == "system_tools":
        page_placeholder("🛠️ 系統維護")

    elif step == "dev_test":
        page_placeholder("🧪 開發測試")

    else:
        page_select_store()


# ============================================================
# Main
# ============================================================
def main():
    apply_global_style()
    init_session()
    render_sidebar()
    router()


if __name__ == "__main__":
    main()









