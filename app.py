# ============================================================
# ORIVIA OMS - app.py（瘦身版骨架）
# 只保留：
# 1. 基本設定
# 2. Sidebar
# 3. Router
# 4. Main
# ============================================================

from __future__ import annotations

import streamlit as st

# ============================================================
# Pages - Store
# ============================================================
from oms_pages_store import (
    page_order_entry,
    page_order_history,
    page_stocktake_history,
)

# ============================================================
# Pages - Analysis
# ============================================================
from oms_pages_analysis import (
    page_inventory_analysis,
    page_cost_analysis,
    page_purchase_report,
)

# ============================================================
# Pages - Admin
# ============================================================
from oms_pages_admin import (
    page_vendors,
    page_items,
    page_stores,
    page_brands,
    page_users,
)

# ============================================================
# Pages - Settings
# ============================================================
from oms_pages_settings import (
    page_appearance,
    page_operation_rules,
    page_inventory_rules,
)

# ============================================================
# Pages - System
# ============================================================
from oms_pages_system import (
    page_system_info,
)


# ============================================================
# [A1] Config
# ============================================================
APP_TITLE = "ORIVIA OMS"
APP_ICON = "📦"


# ============================================================
# [A2] Sidebar Menu Map
# ============================================================
MENU_TREE = {
    "門市營運": [
        "叫貨 / 庫存",
        "叫貨紀錄",
        "盤點歷史",
    ],
    "數據分析": [
        "進銷存分析",
        "成本分析",
        "進貨報表",
    ],
    "系統管理": [
        "廠商管理",
        "品項管理",
        "分店管理",
        "品牌管理",
        "帳號權限",
    ],
    "系統設定": [
        "外觀設定",
        "營運規則",
        "庫存規則",
    ],
    "系統資訊": [
        "系統資訊",
    ],
}


# ============================================================
# [A3] Sidebar
# ============================================================
def build_sidebar() -> tuple[str, str]:
    st.sidebar.title(APP_TITLE)

    menu_main = st.sidebar.selectbox(
        "功能分類",
        list(MENU_TREE.keys()),
        index=0,
    )

    menu_sub = st.sidebar.radio(
        "選擇功能",
        MENU_TREE[menu_main],
        index=0,
    )

    return menu_main, menu_sub


# ============================================================
# [A4] Router
# ============================================================
def route_page(menu_sub: str) -> None:
    # Store
    if menu_sub == "叫貨 / 庫存":
        page_order_entry()

    elif menu_sub == "叫貨紀錄":
        page_order_history()

    elif menu_sub == "盤點歷史":
        page_stocktake_history()

    # Analysis
    elif menu_sub == "進銷存分析":
        page_inventory_analysis()

    elif menu_sub == "成本分析":
        page_cost_analysis()

    elif menu_sub == "進貨報表":
        page_purchase_report()

    # Admin
    elif menu_sub == "廠商管理":
        page_vendors()

    elif menu_sub == "品項管理":
        page_items()

    elif menu_sub == "分店管理":
        page_stores()

    elif menu_sub == "品牌管理":
        page_brands()

    elif menu_sub == "帳號權限":
        page_users()

    # Settings
    elif menu_sub == "外觀設定":
        page_appearance()

    elif menu_sub == "營運規則":
        page_operation_rules()

    elif menu_sub == "庫存規則":
        page_inventory_rules()

    # System
    elif menu_sub == "系統資訊":
        page_system_info()

    else:
        st.warning("找不到對應頁面。")


# ============================================================
# [A5] Main
# ============================================================
def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        layout="wide",
    )

    _, menu_sub = build_sidebar()
    route_page(menu_sub)


# ============================================================
# [A6] Run
# ============================================================
if __name__ == "__main__":
    main()
