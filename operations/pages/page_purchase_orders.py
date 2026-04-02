# ============================================================
# ORIVIA OMS
# 檔案：operations/pages/page_purchase_orders.py
# 說明：叫貨單管理頁
# 功能：顯示盤點流程自動產生的 draft PO，支援篩選、展開明細、單張確認。
# 注意：本頁只做查看與確認，不做編輯、刪除、送單。
# ============================================================

"""
頁面模組：叫貨單管理頁。
由 page_stocktake 盤點送出後自動建立的 draft purchase_orders 在此確認。
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from operations.logic.logic_purchase_orders import confirm_purchase_order, load_po_list


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
_STATUS_OPTIONS = ["draft", "confirmed", "全部"]
_STATUS_LABEL = {
    "draft": "🟡 待確認",
    "confirmed": "✅ 已確認",
}
_MAX_PO_DISPLAY = 20


# ----------------------------------------------------------
# 內部 UI 工具
# ----------------------------------------------------------

def _fmt_amount(val) -> str:
    """amount = 0 顯示 —；否則顯示數值。"""
    try:
        f = float(val)
    except (TypeError, ValueError):
        return "—"
    if f == 0:
        return "—"
    return str(round(f, 1))


# ----------------------------------------------------------
# [S2] PO 明細區塊（expander 展開後）
# ----------------------------------------------------------
def _render_po_lines(po_id: str, pol_df, stocktake_id: str) -> None:
    """展開後的明細品項清單。"""
    if pol_df.empty or "po_id" not in pol_df.columns:
        st.caption("無明細資料")
        if stocktake_id:
            st.caption(f"來源盤點：{stocktake_id}")
        return

    lines = pol_df[pol_df["po_id"].astype(str).str.strip() == str(po_id).strip()]
    if lines.empty:
        st.caption("無明細資料")
        if stocktake_id:
            st.caption(f"來源盤點：{stocktake_id}")
        return

    # 表頭列
    h0, h1, h2, h3, h4 = st.columns([4, 2, 2, 2, 2])
    with h0:
        st.caption("**品項**")
    with h1:
        st.caption("**叫貨量**")
    with h2:
        st.caption("**單位**")
    with h3:
        st.caption("**基礎量**")
    with h4:
        st.caption("**金額**")

    # 明細列
    for _, row in lines.iterrows():
        c0, c1, c2, c3, c4 = st.columns([4, 2, 2, 2, 2])
        with c0:
            st.markdown(str(row.get("item_name", "")))
        with c1:
            st.markdown(str(row.get("order_qty", "")))
        with c2:
            st.markdown(str(row.get("order_unit", row.get("unit_id", ""))))
        with c3:
            st.markdown(str(row.get("base_qty", "")))
        with c4:
            st.markdown(_fmt_amount(row.get("amount", 0)))

    # 來源盤點標記
    if stocktake_id:
        st.caption(f"來源盤點：{stocktake_id}")


# ----------------------------------------------------------
# [S3] 單張 PO 列（expander + 確認按鈕）
# ----------------------------------------------------------
def _render_po_row(row, pol_df, vendor_map: dict, actor: str) -> None:
    """每張 PO 的可展開列。"""
    po_id = str(row.get("po_id", "")).strip()
    vendor_id = str(row.get("vendor_id", "")).strip()
    vendor_name = vendor_map.get(vendor_id, vendor_id)
    status = str(row.get("status", "")).strip()
    po_date = str(row.get("po_date", "")).strip()
    stocktake_id = str(row.get("stocktake_id", "")).strip()

    # 明細筆數
    if not pol_df.empty and "po_id" in pol_df.columns:
        line_count = len(
            pol_df[pol_df["po_id"].astype(str).str.strip() == po_id]
        )
    else:
        line_count = 0

    status_label = _STATUS_LABEL.get(status, status)
    expander_title = (
        f"{po_id}　{vendor_name}　{line_count} 品項　{po_date}　{status_label}"
    )

    with st.expander(expander_title, expanded=False):
        _render_po_lines(po_id, pol_df, stocktake_id)

        st.divider()

        if status == "draft":
            if st.button(
                "✅ 確認叫貨單",
                key=f"confirm_{po_id}",
                use_container_width=True,
            ):
                result = confirm_purchase_order(po_id, actor)
                if result["ok"]:
                    st.success("✅ 叫貨單已確認")
                    st.rerun()
                else:
                    st.error(f"❌ 確認失敗：{result['error']}")
        else:
            st.success("✅ 已確認")


# ----------------------------------------------------------
# [S4] 叫貨單管理主畫面
# ----------------------------------------------------------
def render_po_management(store_id: str, actor: str) -> None:
    """叫貨單管理主畫面（含篩選、列表、明細展開）。"""
    _apply_compact_style()

    st.title("叫貨單管理")

    # 篩選列
    col_status, col_date = st.columns([1, 1])
    with col_status:
        status_filter = st.selectbox(
            "狀態",
            _STATUS_OPTIONS,
            index=0,
            key="po_mgmt_status_filter",
        )
    with col_date:
        filter_date = st.date_input(
            "日期",
            value=date.today(),
            key="po_mgmt_filter_date",
        )

    po_df, pol_df, vendor_map = load_po_list(
        store_id=store_id,
        status_filter=str(status_filter),
        filter_date=filter_date,
    )

    if po_df.empty:
        st.info(f"（{filter_date}）尚無符合條件的叫貨單")
        return

    total = len(po_df)
    if total > _MAX_PO_DISPLAY:
        st.warning(
            f"顯示前 {_MAX_PO_DISPLAY} 筆，共 {total} 筆，請縮小篩選範圍"
        )
        po_df = po_df.head(_MAX_PO_DISPLAY)

    for _, row in po_df.iterrows():
        _render_po_row(row, pol_df, vendor_map, actor)


# ----------------------------------------------------------
# [S5] 頁面入口（給 router 用）
# ----------------------------------------------------------
def page_purchase_orders() -> None:
    """叫貨單管理頁入口。"""
    store_id = str(st.session_state.get("store_id", "")).strip()
    actor = str(st.session_state.get("role", "")).strip()
    render_po_management(store_id, actor)
