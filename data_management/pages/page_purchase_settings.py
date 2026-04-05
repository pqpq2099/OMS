# ============================================================
# ORIVIA OMS
# 檔案：pages/page_purchase_settings.py
# 說明：採購設定主入口頁
# 功能：整合廠商、品項、價格、單位與單位換算五個子頁模組
# ============================================================

"""
頁面模組：採購設定 / 資料管理。

目前版本先專注主資料管理：
1. 廠商管理
2. 品項管理
3. 價格管理
4. 單位管理
5. 單位換算

本檔只保留主入口與頁籤切換。
各子頁邏輯已拆到 pages/purchase_settings/ 內，方便後續獨立維護。
"""

from __future__ import annotations

import streamlit as st

from shared.utils.permissions import require_permission
from data_management.pages.purchase_settings.tab_items import _tab_items
from data_management.pages.purchase_settings.tab_prices import _tab_prices
from data_management.pages.purchase_settings.tab_unit_conversions import _tab_unit_conversions
from data_management.pages.purchase_settings.tab_units import _tab_units
from data_management.pages.purchase_settings.tab_vendors import _tab_vendors


def page_purchase_settings():
    if not require_permission("data.purchase.manage"):
        return
    st.title("🛒 採購設定")
    st.caption("目前先以 item-only 模型管理主資料：廠商、品項、價格、單位、單位換算。")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["廠商管理", "品項管理", "價格管理", "單位管理", "單位換算"]
    )

    with tab1:
        _tab_vendors()

    with tab2:
        _tab_items()

    with tab3:
        _tab_prices()

    with tab4:
        _tab_units()

    with tab5:
        _tab_unit_conversions()
