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
    page_select_store,
    page_select_vendor,
)

from pages_reports import (
    page_analysis,
    page_cost_debug,
    page_export,
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


def save_setting(setting_key: str, setting_value: str) -> None:
    """
    將設定寫回 settings 表。
    規則：
    - 有 system_name 就更新
    - 沒有就新增一列
    """
    settings_df = read_table("settings").copy()

    # 如果 settings 表完全是空的，先建立最基本結構
    if settings_df.empty:
        settings_df = pd.DataFrame(columns=["key", "value"])

    settings_df.columns = [str(c).strip() for c in settings_df.columns]
    key_col, value_col = _get_settings_key_value_cols(settings_df)

    # 如果現有 settings 欄位不符合，就用最簡單 key/value 結構
    if not key_col or not value_col:
        settings_df = pd.DataFrame(columns=["key", "value"])
        key_col = "key"
        value_col = "value"

    work = settings_df.copy()
    work.columns = [str(c).strip() for c in work.columns]

    mask = work[key_col].astype(str).str.strip().str.lower() == setting_key.lower()

    if mask.any():
        work.loc[mask, value_col] = setting_value
    else:
        new_row = {c: "" for c in work.columns}
        new_row[key_col] = setting_key
        new_row[value_col] = setting_value
        work = pd.concat([work, pd.DataFrame([new_row])], ignore_index=True)

    header = get_header("settings")
    if not header:
        # 如果抓不到 header，就退回目前欄位
        header = list(work.columns)

    # 對齊 header，避免 append_rows_by_header 寫壞
    for c in header:
        if c not in work.columns:
            work[c] = ""

    work = work[header].copy()

    # 這裡用覆蓋型重寫策略：
    # 先清 cache，再直接把 settings 表全部內容重寫
    # 若你的 oms_core 沒有 overwrite function，這版先改成：
    # 1) 若 key 已存在則只新增一筆會重複，不理想
    # 因此這邊改用 Google Sheet 最穩邏輯：透過 get_header + append_rows_by_header 不足以更新舊列
    # 所以此版本採「若已存在就提示需要 update support」會較安全
    #
    # 但為了讓你先看 UI，這裡先用簡化策略：
    # - 若已存在 system_name，仍新增一筆最新值
    # - get_system_name() 讀取時抓第一筆命中值
    # 會導致舊值殘留，不理想
    #
    # 因此這裡改成：如果 settings 表目前已有 key/value 結構，就只允許新增第一筆；
    # 若已有 system_name，則直接拋出訊息提示需後續補 update function。
    #
    # 為了避免你現在寫壞表，先做安全版：
    existing = settings_df.copy()
    existing.columns = [str(c).strip() for c in existing.columns]
    existing_key_col, _ = _get_settings_key_value_cols(existing)

    if existing_key_col and not existing.empty:
        existing_mask = existing[existing_key_col].astype(str).str.strip().str.lower() == setting_key.lower()
        if existing_mask.any():
            raise ValueError("目前 settings 更新功能尚未支援覆寫舊值，請先刪除舊的 system_name 再儲存一次。")

    row_to_append = {c: "" for c in header}
    row_to_append[key_col] = setting_key
    row_to_append[value_col] = setting_value

    append_rows_by_header("settings", header, [row_to_append])
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
        # 作業管理
        # ====================================================
        st.markdown("### 作業管理")

        if st.button("🏠 選擇分店", use_container_width=True, key="sb_select_store"):
            st.session_state.step = "select_store"
            st.rerun()

        if st.session_state.store_id:
            if st.button("🏢 分店功能選單", use_container_width=True, key="sb_select_vendor"):
                st.session_state.step = "select_vendor"
                st.rerun()

        if st.session_state.vendor_id:
            if st.button("📝 叫貨 / 庫存", use_container_width=True, key="sb_order_entry"):
                st.session_state.step = "order_entry"
                st.rerun()

        if st.session_state.store_id:
            if st.button("📋 今日進貨明細", use_container_width=True, key="sb_export"):
                st.session_state.step = "export"
                st.rerun()

        # ====================================================
        # 報表分析
        # ====================================================
        if role in ["owner", "admin", "store_manager"]:
            st.markdown("### 報表分析")

            if st.session_state.store_id:
                if st.button("🧾 歷史叫貨紀錄", use_container_width=True, key="sb_purchase_history"):
                    st.session_state.step = "purchase_history"
                    st.rerun()

                if st.button("📈 進銷存分析", use_container_width=True, key="sb_analysis"):
                    st.session_state.step = "analysis"
                    st.rerun()

                if st.button("📜 歷史紀錄", use_container_width=True, key="sb_view_history"):
                    st.session_state.step = "view_history"
                    st.rerun()

                if st.button("📤 資料匯出", use_container_width=True, key="sb_data_export"):
                    st.session_state.step = "data_export"
                    st.rerun()

        # ====================================================
        # 後台管理
        # ====================================================
        if role in ["owner", "admin"]:
            st.markdown("### 後台管理")

            if st.button("👥 使用者權限", use_container_width=True, key="sb_user_admin"):
                st.session_state.step = "user_admin"
                st.rerun()

            if st.button("🛒 採購設定", use_container_width=True, key="sb_purchase_settings"):
                st.session_state.step = "purchase_settings"
                st.rerun()

            if st.button("🧮 成本檢查", use_container_width=True, key="sb_cost_debug"):
                st.session_state.step = "cost_debug"
                st.rerun()

            if st.button("🎨 系統外觀", use_container_width=True, key="sb_appearance_settings"):
                st.session_state.step = "appearance_settings"
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
        page_placeholder("🛒 採購設定")

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
