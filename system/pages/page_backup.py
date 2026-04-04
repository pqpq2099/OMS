from __future__ import annotations

# ============================================================
# ORIVIA OMS
# 檔案：system/pages/page_backup.py
# 說明：備份歷史交易紀錄 — 產生 Excel 供下載，供系統初始化後還原用
# 權限：manage_system（owner 限定）
# ============================================================

import io
from datetime import datetime

import pandas as pd
import streamlit as st

from shared.services.data_backend import read_table
from users_permissions.services.service_role_permission import has_permission

# ── 備份資料表清單 ─────────────────────────────────────────────
# (table_name, sheet_name, category)
_BACKUP_TABLES: list[tuple[str, str, str]] = [
    # 交易紀錄
    ("stocktakes",           "盤點單",     "交易"),
    ("stocktake_lines",      "盤點明細",   "交易"),
    ("purchase_orders",      "叫貨單",     "交易"),
    ("purchase_order_lines", "叫貨明細",   "交易"),
    ("transactions",         "流水帳",     "交易"),
    ("stock_adjustments",    "庫存調整",   "交易"),
    ("stock_transfers",      "調貨單",     "交易"),
    ("stock_transfer_lines", "調貨明細",   "交易"),
    ("audit_logs",           "操作稽核",   "交易"),
    # 主資料
    ("items",                "品項",       "主資料"),
    ("item_specs",           "品項規格",   "主資料"),
    ("brands",               "品牌",       "主資料"),
    ("units",                "單位",       "主資料"),
    ("unit_conversions",     "換算規則",   "主資料"),
    ("prices",               "價格",       "主資料"),
    ("stores",               "分店",       "主資料"),
    ("vendors",              "廠商",       "主資料"),
]


def _build_backup_excel() -> bytes:
    """讀取所有備份表，輸出為 Excel bytes（openpyxl 引擎）。"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for table_name, sheet_name, _ in _BACKUP_TABLES:
            try:
                df = read_table(table_name)
            except Exception:
                df = pd.DataFrame()
            # 空表仍寫一個只有欄位名稱的 sheet（或空 sheet）
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    return output.getvalue()


def page_backup():
    st.markdown(
        "<style>.block-container { padding-top: 4rem !important; }</style>",
        unsafe_allow_html=True,
    )
    st.title("📦 備份歷史交易紀錄")

    # ── 權限守衛 ──────────────────────────────────────────────
    if not has_permission("manage_system"):
        st.error("此功能限系統管理員使用。")
        return

    st.caption("將所有交易紀錄與主資料匯出為 Excel 檔案，供系統初始化後還原使用。")
    st.markdown("---")

    # ── 備份說明 ──────────────────────────────────────────────
    txn_tables  = [(n, s) for n, s, c in _BACKUP_TABLES if c == "交易"]
    ref_tables  = [(n, s) for n, s, c in _BACKUP_TABLES if c == "主資料"]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📋 交易紀錄**")
        for _, sheet in txn_tables:
            st.caption(f"• {sheet}")
    with col2:
        st.markdown("**🗂 主資料**")
        for _, sheet in ref_tables:
            st.caption(f"• {sheet}")

    st.markdown("---")

    # ── 產生下載 ──────────────────────────────────────────────
    now_str = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"OMS_backup_{now_str}.xlsx"

    st.info(
        "點擊下方按鈕產生備份檔案。資料量較大時可能需要數秒，請耐心等候。",
        icon="ℹ️",
    )

    if st.button("🔄 產生備份檔案", use_container_width=True, key="backup_generate"):
        with st.spinner("正在讀取資料並產生 Excel…"):
            try:
                excel_bytes = _build_backup_excel()
                st.session_state["_backup_excel_bytes"] = excel_bytes
                st.session_state["_backup_filename"] = filename
                st.success(f"備份完成，共 {len(_BACKUP_TABLES)} 個工作表。")
            except Exception as e:
                st.error(f"產生備份時發生錯誤：{e}")
                st.session_state.pop("_backup_excel_bytes", None)

    if "_backup_excel_bytes" in st.session_state:
        st.download_button(
            label="⬇️ 下載 Excel 備份檔",
            data=st.session_state["_backup_excel_bytes"],
            file_name=st.session_state.get("_backup_filename", filename),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="backup_download",
        )
