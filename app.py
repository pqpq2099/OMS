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
    read_table,
)

from pages.page_order_entry import (
    page_order_entry,
    page_order_message_detail,
    page_select_store,
    page_select_vendor,
)

from pages.page_reports import (
    page_analysis,
    page_cost_debug,
    page_export,
    page_view_history,
)

from pages.page_purchase_settings import page_purchase_settings
from pages.page_user_admin import page_user_admin
st.set_page_config(page_title="營運管理系統", layout="centered")



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

    # 先用假角色測試，之後再接 users / roles
    if "role" not in st.session_state:
        st.session_state.role = "owner"  # owner / admin / store_manager / leader



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

    creds = Credentials.from_service_account_file(
        "service_account.json",
        scopes=scope,
    )

    gc = gspread.authorize(creds)

    SHEET_ID = "1L1ogNjLWjjH8usMWC2JQowMMZkfD4zkuE-4UcgiTqXQ"
    sheet = gc.open_by_key(SHEET_ID).worksheet("settings")
    
    rows = [settings_df.columns.tolist()] + settings_df.astype(str).values.tolist()
    
    sheet.clear()
    sheet.update(rows)
    
    bust_cache()



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

# ============================================================
# [S1] Sidebar 側邊欄
# 你最常改的地方之一：
# 1. 側邊欄分組順序
# 2. 哪些按鈕顯示給哪些角色
# 3. 每個按鈕按下後要切到哪個 step
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
        # 這一區放日常操作頁
        # ====================================================
        st.markdown("### 作業")

        if st.button("🏠 選擇分店", use_container_width=True, key="sb_select_store"):
            st.session_state.step = "select_store"
            st.rerun()

        # ====================================================
        # 叫貨明細
        # 顯示今日叫貨整理與 LINE 訊息格式
        # ====================================================
        if st.button("📩 叫貨明細", use_container_width=True, key="sb_order_message_detail"):
            st.session_state.step = "order_message_detail"
            st.rerun()
                
        st.markdown("---")

        # ====================================================
        # 分析
        # 這一區放報表 / 歷史 / 分析
        # ====================================================
        st.markdown("### 分析")

        if st.button("📊 進銷存分析", use_container_width=True, key="sb_analysis"):
            st.session_state.step = "analysis"
            st.rerun()

        if st.button("📜 進貨分析", use_container_width=True, key="sb_view_history"):
            st.session_state.step = "view_history"
            st.rerun()

        if st.button("🧾 叫貨歷史", use_container_width=True, key="sb_purchase_history"):
            st.session_state.step = "purchase_history"
            st.rerun()

        st.markdown("---")

        # ====================================================
        # 資料管理
        # 這一區放主資料維護
        # 目前先統一進同一頁，之後再拆成廠商 / 品項 / 價格
        # ====================================================
        st.markdown("### 資料管理")

        if st.button("🛒 資料管理", use_container_width=True, key="sb_purchase_settings"):
            st.session_state.step = "purchase_settings"
            st.rerun()

        st.markdown("---")

        # ====================================================
        # 使用者與權限
        # 這一區放帳號 / 分店指派 / 權限管理
        # ====================================================
        st.markdown("### 使用者與權限")

        if st.button("👥 使用者權限", use_container_width=True, key="sb_user_admin"):
            st.session_state.step = "user_admin"
            st.rerun()

        st.markdown("---")

        # ====================================================
        # 系統
        # 這一區放系統層級功能
        # ====================================================
        if role == "owner":
            st.markdown("### 系統")

            if st.button("🎨 外觀設定", use_container_width=True, key="sb_appearance_settings"):
                st.session_state.step = "appearance_settings"
                st.rerun()

            if st.button("🛠️ 系統維護", use_container_width=True, key="sb_system_tools"):
                st.session_state.step = "system_tools"
                st.rerun()

            if st.button("🧪 開發測試", use_container_width=True, key="sb_dev_test"):
                st.session_state.step = "dev_test"
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
        page_user_admin()

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









