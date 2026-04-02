# ============================================================
# ORIVIA OMS
# 檔案：operations/pages/page_stocktake_history.py
# 說明：盤點歷史查詢頁（read-only）
# 功能：依日期與廠商查看 stocktakes + stocktake_lines，顯示對應 PO 狀態。
# 注意：本頁嚴格 read-only，不含任何寫入操作。
# ============================================================

"""
頁面模組：盤點歷史查詢頁。
查看盤點紀錄與對應叫貨單狀態，不做任何編輯。
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from operations.logic.logic_stocktake_history import load_stocktake_history


# ----------------------------------------------------------
# [S1] 手機版 UI 壓縮樣式
# ----------------------------------------------------------
def _apply_compact_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1rem;
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }
        [data-testid="stHorizontalBlock"] {
            gap: 0.4rem;
            flex-wrap: nowrap !important;
            align-items: center !important;
        }
        [data-testid="column"] {
            min-width: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------
# 常數
# ----------------------------------------------------------
_PO_STATUS_LABEL: dict[str, str] = {
    "draft": "🟡 叫貨待確認",
    "confirmed": "✅ 叫貨已確認",
}
_MAX_STK_DISPLAY = 20


# ----------------------------------------------------------
# 內部 UI 工具
# ----------------------------------------------------------

def _fmt_order_qty(val) -> str:
    """order_qty = 0 顯示「—」；否則顯示數值（去除不必要小數點）。"""
    try:
        f = float(val)
    except (TypeError, ValueError):
        return "—"
    if f == 0:
        return "—"
    return str(int(f)) if f == int(f) else str(round(f, 2))


def _po_badge_str(stocktake_id: str, po_map: dict) -> str:
    """依 po_map 回傳 PO 狀態標籤字串。"""
    if stocktake_id not in po_map:
        return "— 無叫貨單"
    _po_id, status = po_map[stocktake_id]
    return _PO_STATUS_LABEL.get(status, f"叫貨單：{status}")


# ----------------------------------------------------------
# [S2] 盤點明細區（expander 展開後）
# ----------------------------------------------------------
def _render_stocktake_lines(
    stocktake_id: str,
    stl_df,
    po_map: dict,
) -> None:
    """展開後顯示品項明細 + PO 資訊。"""
    if stl_df.empty or "stocktake_id" not in stl_df.columns:
        st.caption("無明細資料")
        _render_po_info(stocktake_id, po_map)
        return

    lines = stl_df[
        stl_df["stocktake_id"].astype(str).str.strip() == str(stocktake_id).strip()
    ]
    if lines.empty:
        st.caption("無明細資料")
        _render_po_info(stocktake_id, po_map)
        return

    # 表頭
    h0, h1, h2, h3, h4 = st.columns([4, 2, 2, 2, 2])
    with h0:
        st.caption("**品項**")
    with h1:
        st.caption("**庫存量**")
    with h2:
        st.caption("**庫存單位**")
    with h3:
        st.caption("**叫貨量**")
    with h4:
        st.caption("**叫貨單位**")

    # 明細列
    for _, row in lines.iterrows():
        c0, c1, c2, c3, c4 = st.columns([4, 2, 2, 2, 2])
        with c0:
            st.markdown(str(row.get("item_name", "")))
        with c1:
            _sq = row.get("stock_qty", "")
            try:
                _sqf = float(_sq)
                st.markdown(str(int(_sqf)) if _sqf == int(_sqf) else str(round(_sqf, 2)))
            except (TypeError, ValueError):
                st.markdown(str(_sq))
        with c2:
            st.markdown(str(row.get("stock_unit", row.get("stock_unit_id", ""))))
        with c3:
            st.markdown(_fmt_order_qty(row.get("order_qty", 0)))
        with c4:
            # order_unit_display 由 logic 層預先建立
            st.markdown(str(row.get("order_unit_display", row.get("order_unit_id", ""))))

    # PO 資訊區
    _render_po_info(stocktake_id, po_map)


def _render_po_info(stocktake_id: str, po_map: dict) -> None:
    """明細底部顯示叫貨單資訊。"""
    st.divider()
    if stocktake_id not in po_map:
        st.caption("（本次盤點無叫貨）")
        return
    po_id, status = po_map[stocktake_id]
    label = _PO_STATUS_LABEL.get(status, status)
    st.caption(f"叫貨單：{po_id}　狀態：{label}")


# ----------------------------------------------------------
# [S3] 單筆 stocktake 列（expander）
# ----------------------------------------------------------
def _render_stocktake_row(
    row,
    stl_df,
    po_map: dict,
    vendor_map: dict,
) -> None:
    """每筆盤點的 expander 列。"""
    stk_id = str(row.get("stocktake_id", "")).strip()
    vendor_id = str(row.get("vendor_id", "")).strip()
    vendor_name = vendor_map.get(vendor_id, vendor_id)
    stk_date = str(row.get("stocktake_date", "")).strip()
    po_badge = _po_badge_str(stk_id, po_map)

    # 計算明細筆數
    if not stl_df.empty and "stocktake_id" in stl_df.columns:
        line_count = len(
            stl_df[stl_df["stocktake_id"].astype(str).str.strip() == stk_id]
        )
    else:
        line_count = 0

    expander_title = (
        f"{stk_id}　{vendor_name}　{line_count} 品項　{stk_date}　{po_badge}"
    )

    with st.expander(expander_title, expanded=False):
        _render_stocktake_lines(stk_id, stl_df, po_map)


# ----------------------------------------------------------
# [S4] 盤點歷史主畫面
# ----------------------------------------------------------
def render_stocktake_history(store_id: str) -> None:
    """盤點歷史主畫面（含篩選、列表、明細展開）。"""
    _apply_compact_style()

    st.title("盤點歷史")

    # ── 日期篩選 ──────────────────────────────────────────
    filter_date = st.date_input(
        "日期",
        value=date.today(),
        key="hist_filter_date",
    )

    # ── 載入本日全部盤點（無廠商篩選），取得廠商選單 ──
    stk_all, stl_all, po_map_all, vendor_map, vendor_options = load_stocktake_history(
        store_id=store_id,
        filter_date=filter_date,
        vendor_filter="",
    )

    # ── 廠商篩選 selectbox ──────────────────────────────
    display_options = ["全部"] + [vendor_map.get(vid, vid) for vid in vendor_options]
    selected_display = st.selectbox(
        "廠商",
        display_options,
        index=0,
        key="hist_vendor_filter",
    )

    # ── 依廠商選擇決定使用的資料集 ─────────────────────
    if selected_display == "全部":
        stk_df = stk_all
        stl_df = stl_all
        po_map = po_map_all
    else:
        # 由 display_name 反查 vendor_id
        selected_vid = next(
            (v for v in vendor_options if vendor_map.get(v, v) == selected_display),
            "",
        )
        if selected_vid:
            stk_df, stl_df, po_map, _, _ = load_stocktake_history(
                store_id=store_id,
                filter_date=filter_date,
                vendor_filter=selected_vid,
            )
        else:
            # fallback：找不到 vendor_id 時顯示全部
            stk_df, stl_df, po_map = stk_all, stl_all, po_map_all

    # ── 空列表處理 ────────────────────────────────────────
    if stk_df.empty:
        vendor_hint = "" if selected_display == "全部" else f"{selected_display} "
        st.info(f"（{filter_date}）{vendor_hint}尚無盤點紀錄")
        return

    # ── 筆數上限 ──────────────────────────────────────────
    total = len(stk_df)
    if total > _MAX_STK_DISPLAY:
        st.warning(
            f"顯示前 {_MAX_STK_DISPLAY} 筆，共 {total} 筆，請縮小篩選範圍"
        )
        stk_df = stk_df.head(_MAX_STK_DISPLAY)

    # ── 逐筆渲染 ─────────────────────────────────────────
    for _, row in stk_df.iterrows():
        _render_stocktake_row(row, stl_df, po_map, vendor_map)


# ----------------------------------------------------------
# [S5] 頁面入口（給 router 用）
# ----------------------------------------------------------
def page_stocktake_history() -> None:
    """盤點歷史查詢頁入口。"""
    store_id = str(st.session_state.get("store_id", "")).strip()
    render_stocktake_history(store_id)
