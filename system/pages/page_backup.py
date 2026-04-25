from __future__ import annotations

# ============================================================
# ORIVIA OMS
# 檔案：system/pages/page_backup.py
# 說明：備份歷史交易紀錄 — 產生 Excel 供下載，供系統初始化後還原用
# 權限：system.manage（owner 限定）
# ============================================================

import io
from datetime import datetime

import pandas as pd
import streamlit as st

from shared.services.data_backend import read_table
from system.logic.logic_restore import execute_restore, preview_restore
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
    if not has_permission("system.manage"):
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

    # ── 還原歷史交易 ─────────────────────────────────────────────
    st.markdown("---")
    st.title("📥 還原歷史交易")
    st.warning("此操作會以備份檔內容覆蓋現有資料（依主鍵比對），請確認檔案來源正確。", icon="⚠️")

    uploaded = st.file_uploader(
        "上傳備份檔案（.xlsx）",
        type=["xlsx"],
        key="restore_upload",
    )

    if uploaded is not None:
        file_bytes = uploaded.getvalue()

        # 預覽
        if "_restore_preview" not in st.session_state:
            with st.spinner("正在分析備份檔案…"):
                st.session_state["_restore_preview"] = preview_restore(
                    file_bytes, _BACKUP_TABLES
                )
                st.session_state["_restore_file_bytes"] = file_bytes

        preview = st.session_state.get("_restore_preview", [])

        # 顯示預覽結果
        ok_count = 0
        for item in preview:
            sheet = item["sheet"] or "(unknown)"
            if item["status"] == "ok":
                st.caption(f"✅ {sheet}：{item['count']} 筆")
                ok_count += 1
            elif item["status"] == "skip":
                st.caption(f"⏭️ {sheet}：跳過 — {item['msg']}")
            else:
                st.caption(f"❌ {sheet}：{item['msg']}")

        if ok_count == 0:
            st.error("備份檔中沒有可還原的資料。")
        else:
            st.info(f"共 {ok_count} 張表可還原。", icon="ℹ️")

            if st.button("✅ 確認還原", use_container_width=True, key="restore_confirm"):
                with st.spinner("正在還原資料…"):
                    results = execute_restore(
                        st.session_state["_restore_file_bytes"],
                        _BACKUP_TABLES,
                    )

                # 顯示結果
                done = [r for r in results if r["status"] == "done"]
                fail = [r for r in results if r["status"] == "fail"]
                skip = [r for r in results if r["status"] == "skip"]

                if done:
                    total_rows = sum(r["count"] for r in done)
                    st.success(f"還原完成：{len(done)} 張表，共 {total_rows} 筆。")
                if skip:
                    st.info(f"跳過 {len(skip)} 張表。")
                if fail:
                    for r in fail:
                        st.error(f"❌ {r['sheet']}：{r['msg']}")

                # 清除預覽狀態
                st.session_state.pop("_restore_preview", None)
                st.session_state.pop("_restore_file_bytes", None)

    else:
        # 使用者清除上傳檔案時，重置預覽狀態
        st.session_state.pop("_restore_preview", None)
        st.session_state.pop("_restore_file_bytes", None)
