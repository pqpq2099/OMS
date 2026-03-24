from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from services import service_order


def page_order_message_detail():
    st.title("🧾 叫貨明細")

    store_id = st.session_state.get("store_id", "")
    store_name = st.session_state.get("store_name", "")

    if not store_id:
        st.warning("請先選擇分店")
        return

    selected_date = st.date_input(
        "日期",
        value=date.today(),
        key="order_message_detail_date",
    )
    # 叫貨明細頁一律只顯示「今天到貨」的資料。
    # 不再提前顯示隔天到貨，也不再補抓前一天建立、今天才到貨以外的混合提醒邏輯。

    page_tables = service_order.load_order_page_tables()
    po_df = page_tables["purchase_orders"]
    pol_df = page_tables["purchase_order_lines"]
    vendors_df = page_tables["vendors"]
    items_df = page_tables["items"]

    if po_df.empty or pol_df.empty:
        st.info("目前沒有叫貨資料")
        return

    po_df = po_df.copy()
    if "order_date" not in po_df.columns:
        st.error("purchase_orders 缺少 order_date 欄位")
        return

    po_df["order_date_dt"] = pd.to_datetime(po_df["order_date"], errors="coerce").dt.date
    if "delivery_date" in po_df.columns:
        po_df["delivery_date_dt"] = pd.to_datetime(po_df["delivery_date"], errors="coerce").dt.date
    elif "expected_date" in po_df.columns:
        po_df["delivery_date_dt"] = pd.to_datetime(po_df["expected_date"], errors="coerce").dt.date
    else:
        po_df["delivery_date_dt"] = po_df["order_date_dt"]

    if "store_id" not in po_df.columns or "po_id" not in po_df.columns:
        st.error("purchase_orders 缺少 store_id 或 po_id 欄位")
        return

    po_df["store_id"] = po_df["store_id"].astype(str).str.strip()
    po_df["po_id"] = po_df["po_id"].astype(str).str.strip()
    base_mask = po_df["store_id"] == str(store_id).strip()

    po_today = po_df[
        base_mask
        & (po_df["delivery_date_dt"] == selected_date)
    ].copy()

    po_today = po_today.drop_duplicates(subset=["po_id"], keep="first")

    if po_today.empty:
        st.info("這一天沒有叫貨紀錄")
        return

    if "po_id" not in pol_df.columns:
        st.error("purchase_order_lines 缺少 po_id 欄位")
        return

    po_ids = po_today["po_id"].astype(str).tolist()
    pol_df = pol_df.copy()
    pol_df["po_id"] = pol_df["po_id"].astype(str).str.strip()
    lines_today = pol_df[pol_df["po_id"].isin(po_ids)].copy()

    if lines_today.empty:
        st.info("這一天沒有叫貨明細")
        return

    vendor_name_col = "vendor_name_zh" if "vendor_name_zh" in vendors_df.columns else "vendor_name"
    vendor_map = {}
    if not vendors_df.empty and "vendor_id" in vendors_df.columns:
        for _, r in vendors_df.iterrows():
            vid = str(r.get("vendor_id", "")).strip()
            display_name = str(r.get(vendor_name_col, "")).strip() if vendor_name_col in vendors_df.columns else ""
            if not display_name:
                display_name = str(r.get("vendor_name", "")).strip() or vid
            vendor_map[vid] = display_name

    item_name_col = "item_name_zh" if "item_name_zh" in items_df.columns else ("item_name" if "item_name" in items_df.columns else None)
    item_map = {}
    if "item_id" in items_df.columns:
        for _, r in items_df.iterrows():
            iid = str(r.get("item_id", "")).strip()
            display_name = str(r.get(item_name_col, "")).strip() if item_name_col else ""
            item_map[iid] = display_name or iid

    merged = lines_today.merge(
        po_today[["po_id", "vendor_id", "delivery_date_dt"]],
        on="po_id",
        how="left",
        suffixes=("", "_po"),
    )

    vendor_id_col = None
    for c in ["vendor_id_po", "vendor_id_y", "vendor_id", "vendor_id_x"]:
        if c in merged.columns:
            vendor_id_col = c
            break
    if vendor_id_col is None:
        st.error("合併後找不到 vendor_id 欄位")
        return

    merged["vendor_name"] = merged[vendor_id_col].astype(str).str.strip().map(vendor_map).fillna("未分類廠商")
    merged["item_name"] = merged["item_id"].astype(str).str.strip().map(item_map).fillna(merged["item_id"].astype(str))

    qty_col = "order_qty" if "order_qty" in merged.columns else "qty"
    unit_col = "order_unit" if "order_unit" in merged.columns else "unit_id"
    if qty_col not in merged.columns or unit_col not in merged.columns:
        st.error("purchase_order_lines 缺少數量或單位欄位")
        return

    merged[qty_col] = pd.to_numeric(merged[qty_col], errors="coerce").fillna(0)
    merged = merged[merged[qty_col] > 0].copy()
    if merged.empty:
        st.info("這一天目前沒有需要顯示的品項")
        return

    def _fmt_qty(v):
        try:
            v = float(v)
            return str(int(v)) if v.is_integer() else f"{v:.1f}"
        except Exception:
            return str(v)

    def _fmt_line_date(d):
        try:
            weekday_map = ["一", "二", "三", "四", "五", "六", "日"]
            return f"{d.month}/{d.day}（{weekday_map[d.weekday()]}）"
        except Exception:
            return str(d)

    def _get_store_short_name(name: str) -> str:
        name = str(name or "").strip()
        return name[:-1] if name.endswith("店") else name

    def _simplify_line_item_name(name: str) -> str:
        text = str(name or "").strip()
        text = text.replace(" / ", " ")
        text = text.replace("/熟", "(熟)")
        text = text.replace("/生", "(生)")
        return text

    def _fmt_arrival_text(arrival_date_value):
        weekday_map_for_arrival = {0: "一", 1: "二", 2: "三", 3: "四", 4: "五", 5: "六", 6: "日"}
        try:
            if pd.isna(arrival_date_value):
                return "謝謝"
            return f"禮拜{weekday_map_for_arrival[arrival_date_value.weekday()]}到，謝謝"
        except Exception:
            return "謝謝"

    lines = []
    store_short_name = _get_store_short_name(store_name)
    lines.append(_fmt_line_date(selected_date))
    lines.append("")

    merged = merged.sort_values(
        by=["vendor_name", "delivery_date_dt", "item_name"],
        ascending=[True, True, True],
        na_position="last",
    ).reset_index(drop=True)

    for (vendor_name, delivery_dt), group in merged.groupby(["vendor_name", "delivery_date_dt"], sort=False, dropna=False):
        show_vendor = str(vendor_name).strip() if str(vendor_name).strip() else "未分類廠商"
        lines.append(show_vendor)

        if store_short_name:
            lines.append(store_short_name)

        for _, r in group.iterrows():
            item_name = _simplify_line_item_name(r.get("item_name", ""))
            qty = _fmt_qty(r.get(qty_col, ""))
            unit = str(r.get(unit_col, "")).strip()
            lines.append(f"{item_name} {qty}{unit}")

        lines.append(_fmt_arrival_text(delivery_dt))
        lines.append("")

    line_message = "\n".join(lines).strip()

    st.markdown("### LINE 顯示內容")
    st.code(line_message, language="text")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("📤 發送到 LINE", type="primary", use_container_width=True):
            ok = service_order.send_line_message(line_message)
            if ok:
                st.success("✅ 已成功發送到 LINE")
            else:
                st.error("❌ LINE 發送失敗，請檢查 line_bot / line_groups 設定")

    with c2:
        if st.button("⬅️ 返回功能選單", use_container_width=True, key="back_from_order_message_detail"):
            st.session_state.step = "select_vendor"
            st.rerun()
