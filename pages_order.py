from __future__ import annotations

from datetime import date

import streamlit as st

from oms_core import (
    _build_latest_item_metrics_df,
    _clean_option_list,
    _get_active_df,
    _get_last_po_summary,
    _get_latest_stock_qty_in_display_unit,
    _get_latest_price_for_item,
    _item_display_name,
    _label_store,
    _label_vendor,
    _norm,
    _safe_float,
    _sort_items_for_operation,
    _status_hint,
    _now_ts,
    allocate_ids,
    append_rows_by_header,
    bust_cache,
    get_header,
    read_table,
)
from oms_engine import convert_to_base


# ============================================================
# [E1] Select Store
# ============================================================
def page_select_store():
    st.markdown("<style>.block-container { padding-top: 4rem !important; }</style>", unsafe_allow_html=True)
    st.title("🏠 選擇分店")

    stores_df = _get_active_df(read_table("stores"))
    if stores_df.empty:
        st.warning("⚠️ 分店資料讀取失敗")
        return

    stores_df = stores_df.copy()
    stores_df["store_label"] = stores_df.apply(_label_store, axis=1)

    for _, row in stores_df.iterrows():
        label = row["store_label"]
        store_id = _norm(row.get("store_id", ""))
        if st.button(f"📍 {label}", key=f"store_{store_id}", use_container_width=True):
            st.session_state.store_id = store_id
            st.session_state.store_name = label
            st.session_state.vendor_id = ""
            st.session_state.vendor_name = ""
            st.session_state.step = "select_vendor"
            st.rerun()


# ============================================================
# [E2] Select Vendor
# ============================================================
def page_select_vendor():
    st.markdown("<style>.block-container { padding-top: 4rem !important; }</style>", unsafe_allow_html=True)
    st.title(f"🏢 {st.session_state.store_name}")

    st.session_state.record_date = st.date_input("🗓️ 作業日期", value=st.session_state.record_date)

    vendors_df = _get_active_df(read_table("vendors"))
    items_df = _get_active_df(read_table("items"))

    if vendors_df.empty or items_df.empty:
        st.warning("⚠️ 廠商或品項資料讀取失敗")
        return

    item_vendor_ids = set(items_df.get("default_vendor_id", []).astype(str).str.strip())
    vendors = vendors_df[vendors_df["vendor_id"].astype(str).str.strip().isin(item_vendor_ids)].copy()

    if vendors.empty:
        st.warning("⚠️ 目前沒有可用廠商")
        return

    vendors["vendor_label"] = vendors.apply(_label_vendor, axis=1)
    vendors = vendors.sort_values(by=["vendor_label"], ascending=True).reset_index(drop=True)

    for i in range(0, len(vendors), 2):
        cols = st.columns(2)

        left = vendors.iloc[i]
        with cols[0]:
            if st.button(f"📦 {left['vendor_label']}", key=f"vendor_{left.get('vendor_id','')}", use_container_width=True):
                st.session_state.vendor_id = _norm(left.get("vendor_id", ""))
                st.session_state.vendor_name = left["vendor_label"]
                st.session_state.step = "order_entry"
                st.rerun()

        if i + 1 < len(vendors):
            right = vendors.iloc[i + 1]
            with cols[1]:
                if st.button(f"📦 {right['vendor_label']}", key=f"vendor_{right.get('vendor_id','')}", use_container_width=True):
                    st.session_state.vendor_id = _norm(right.get("vendor_id", ""))
                    st.session_state.vendor_name = right["vendor_label"]
                    st.session_state.step = "order_entry"
                    st.rerun()

    st.write("<b>📊 報表與分析中心</b>", unsafe_allow_html=True)

    if st.button("📋 產生今日進貨明細", type="primary", use_container_width=True):
        st.session_state.step = "export"
        st.rerun()

    if st.button("📈 期間進銷存分析", use_container_width=True):
        st.session_state.step = "analysis"
        st.rerun()

    if st.button("🧮 成本檢查", use_container_width=True):
        st.session_state.step = "cost_debug"
        st.rerun()

    if st.button("📜 查看分店歷史紀錄", use_container_width=True):
        st.session_state.step = "view_history"
        st.rerun()

    if st.button("⬅️ 返回分店列表", use_container_width=True):
        st.session_state.step = "select_store"
        st.rerun()


# ============================================================
# [E3] Order Entry
# ============================================================
def page_order_entry():
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem !important;
            padding-left: 0.35rem !important;
            padding-right: 0.35rem !important;
        }

        [data-testid='stHorizontalBlock'] {
            display: flex !important;
            flex-flow: row nowrap !important;
            align-items: flex-start !important;
            gap: 0.35rem !important;
        }

        div[data-testid='stHorizontalBlock'] > div:nth-child(1) {
            flex: 1 1 auto !important;
            min-width: 0px !important;
        }

        div[data-testid='stHorizontalBlock'] > div:nth-child(2),
        div[data-testid='stHorizontalBlock'] > div:nth-child(3) {
            flex: 0 0 84px !important;
            min-width: 84px !important;
            max-width: 84px !important;
        }

        div[data-testid='stNumberInput'] label {
            display: none !important;
        }

        div[data-testid="stNumberInput"] input {
            text-align: center !important;
            padding-left: 0.4rem !important;
            padding-right: 0.4rem !important;
        }

        .order-divider {
            margin: 10px 0 14px 0;
            border-top: 1px solid rgba(128,128,128,0.25);
        }

        .order-meta {
            font-size: 0.82rem;
            color: rgba(220, 225, 235, 0.95);
            margin-top: -0.2rem;
            margin-bottom: 0.2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title(f"📝 {st.session_state.vendor_name}")

    items_df = _get_active_df(read_table("items"))
    prices_df = read_table("prices")
    conversions_df = _get_active_df(read_table("unit_conversions"))
    stocktakes_df = read_table("stocktakes")
    stocktake_lines_df = read_table("stocktake_lines")
    po_df = read_table("purchase_orders")
    pol_df = read_table("purchase_order_lines")

    if items_df.empty:
        st.warning("⚠️ 品項資料讀取失敗")
        return

    if "default_vendor_id" not in items_df.columns:
        st.warning("⚠️ items 缺少 default_vendor_id")
        return

    vendor_items = items_df[
        items_df["default_vendor_id"].astype(str).str.strip() == str(st.session_state.vendor_id).strip()
    ].copy()

    if vendor_items.empty:
        st.info("💡 此廠商目前沒有對應品項")
        if st.button("⬅️ 返回功能選單", use_container_width=True):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    vendor_items = _sort_items_for_operation(vendor_items)

    latest_metrics_df = _build_latest_item_metrics_df(
        store_id=st.session_state.store_id,
        as_of_date=st.session_state.record_date,
    )

    latest_metrics_map = {}
    if not latest_metrics_df.empty:
        for _, m in latest_metrics_df.iterrows():
            latest_metrics_map[_norm(m.get("item_id", ""))] = m.to_dict()

    ref_rows = []
    item_meta = {}

    for _, row in vendor_items.iterrows():
        item_id = _norm(row.get("item_id", ""))
        item_name = _item_display_name(row)

        base_unit = _norm(row.get("base_unit", ""))
        stock_unit = _norm(row.get("default_stock_unit", "")) or base_unit
        order_unit = _norm(row.get("default_order_unit", "")) or base_unit
        price = _get_latest_price_for_item(prices_df, item_id, st.session_state.record_date)

        current_stock_qty = _get_latest_stock_qty_in_display_unit(
            stocktakes_df=stocktakes_df,
            stocktake_lines_df=stocktake_lines_df,
            items_df=vendor_items,
            conversions_df=conversions_df,
            store_id=st.session_state.store_id,
            item_id=item_id,
            display_unit=stock_unit,
        )

        metric = latest_metrics_map.get(item_id, {})
        period_purchase = _safe_float(metric.get("期間進貨", 0))
        period_usage = _safe_float(metric.get("期間消耗", 0))
        daily_avg = _safe_float(metric.get("日平均", 0))
        total_stock_ref = _safe_float(metric.get("庫存合計", 0))
        suggest_qty = round(daily_avg * 1.5, 1)
        status_hint = _status_hint(total_stock_ref, daily_avg, suggest_qty)

        if period_purchase > 0 or period_usage > 0:
            ref_rows.append(
                {
                    "品項名稱": item_name,
                    "上次叫貨": round(period_purchase, 1),
                    "期間消耗": round(period_usage, 1),
                }
            )

        orderable_units_raw = _norm(row.get("orderable_units", ""))
        orderable_unit_options = [u.strip() for u in orderable_units_raw.split(",") if u.strip()]

        if order_unit and order_unit not in orderable_unit_options:
            orderable_unit_options.insert(0, order_unit)

        if not orderable_unit_options:
            orderable_unit_options = [order_unit] if order_unit else [base_unit]

        item_meta[item_id] = {
            "item_name": item_name,
            "base_unit": base_unit,
            "stock_unit": stock_unit,
            "order_unit": order_unit,
            "orderable_unit_options": orderable_unit_options,
            "price": round(price, 1),
            "current_stock_qty": round(current_stock_qty, 1),
            "total_stock_ref": round(total_stock_ref, 1),
            "daily_avg": round(daily_avg, 1),
            "suggest_qty": suggest_qty,
            "status_hint": status_hint,
        }

    ref_df = None
    if ref_rows:
        import pandas as pd
        ref_df = pd.DataFrame(ref_rows).sort_values(["品項名稱"]).reset_index(drop=True)

    with st.expander("📊 查看上次叫貨 / 期間消耗參考（已自動隱藏無紀錄品項）", expanded=False):
        if ref_df is None or ref_df.empty:
            st.caption("目前沒有可參考的資料")
        else:
            for col in ["上次叫貨", "期間消耗"]:
                ref_df[col] = ref_df[col].map(lambda x: f"{x:.1f}")
            st.table(ref_df)

    st.markdown("<div class='order-divider'></div>", unsafe_allow_html=True)

    h1, h2, h3 = st.columns([6, 1, 1])
    h1.write("**品項名稱（建議量=日均×1.5）**")
    h2.write("<div style='text-align:center;'><b>庫</b></div>", unsafe_allow_html=True)
    h3.write("<div style='text-align:center;'><b>進</b></div>", unsafe_allow_html=True)

    with st.form("order_entry_form"):
        submit_rows = []

        for _, row in vendor_items.iterrows():
            item_id = _norm(row.get("item_id", ""))
            meta = item_meta[item_id]

            item_name = meta["item_name"]
            base_unit = meta["base_unit"]
            stock_unit = base_unit
            order_unit = meta["order_unit"]
            current_stock_qty = _safe_float(meta["current_stock_qty"])
            total_stock_ref = _safe_float(meta["total_stock_ref"])
            suggest_qty = _safe_float(meta["suggest_qty"])
            status_hint = _norm(meta["status_hint"])

            c1, c2, c3 = st.columns([6, 1, 1])

            with c1:
                st.write(f"<b>{item_name}</b>", unsafe_allow_html=True)
                tail = f"　{status_hint}" if status_hint else ""
                st.markdown(
                    f"<div class='order-meta'>總庫存：{total_stock_ref:.1f}　建議量：{suggest_qty:.1f}{tail}</div>",
                    unsafe_allow_html=True,
                )

            with c2:
                stock_input = st.number_input(
                    "庫",
                    min_value=0.0,
                    step=0.1,
                    format="%.1f",
                    value=float(current_stock_qty),
                    key=f"stock_{item_id}",
                    label_visibility="collapsed",
                )
                st.caption(base_unit)

            with c3:
                order_input = st.number_input(
                    "進",
                    min_value=0.0,
                    step=0.1,
                    format="%.1f",
                    value=0.0,
                    key=f"order_{item_id}",
                    label_visibility="collapsed",
                )
                selected_order_unit = st.selectbox(
                    "進貨單位",
                    options=meta["orderable_unit_options"],
                    index=meta["orderable_unit_options"].index(order_unit) if order_unit in meta["orderable_unit_options"] else 0,
                    key=f"order_unit_{item_id}",
                    label_visibility="collapsed",
                )

            submit_rows.append(
                {
                    "item_id": item_id,
                    "item_name": item_name,
                    "stock_qty": float(stock_input),
                    "stock_unit": stock_unit,
                    "order_qty": float(order_input),
                    "order_unit": selected_order_unit,
                    "unit_price": float(meta["price"]),
                }
            )

        submitted = st.form_submit_button("💾 儲存庫存並同步叫貨", use_container_width=True)

    if submitted:
        try:
            stocktake_rows = [r for r in submit_rows]
            order_rows = [r for r in submit_rows if r["order_qty"] > 0]

            id_need = {
                "stocktake_id": 1 if stocktake_rows else 0,
                "stocktake_line_id": len(stocktake_rows),
                "po_id": 1 if order_rows else 0,
                "po_line_id": len(order_rows),
            }
            id_map = allocate_ids(id_need)

            now = _now_ts()

            if stocktake_rows:
                stocktake_header = get_header("stocktakes")
                stl_header = get_header("stocktake_lines")

                stocktake_id = id_map["stocktake_id"][0]
                stocktake_main_row = {c: "" for c in stocktake_header}
                for k, v in {
                    "stocktake_id": stocktake_id,
                    "store_id": st.session_state.store_id,
                    "stocktake_date": str(st.session_state.record_date),
                    "status": "done",
                    "note": f"vendor={st.session_state.vendor_id}",
                    "created_at": now,
                    "created_by": "SYSTEM",
                    "updated_at": "",
                    "updated_by": "",
                }.items():
                    if k in stocktake_main_row:
                        stocktake_main_row[k] = v

                append_rows_by_header("stocktakes", stocktake_header, [stocktake_main_row])

                stock_line_rows = []
                for idx, r in enumerate(stocktake_rows):
                    stocktake_line_id = id_map["stocktake_line_id"][idx]

                    try:
                        stock_base_qty, stock_base_unit = convert_to_base(
                            item_id=r["item_id"],
                            qty=r["stock_qty"],
                            from_unit=r["stock_unit"],
                            items_df=vendor_items,
                            conversions_df=conversions_df,
                            as_of_date=st.session_state.record_date,
                        )
                    except Exception:
                        stock_base_qty = r["stock_qty"]
                        stock_base_unit = r["stock_unit"]

                    row_dict = {c: "" for c in stl_header}
                    defaults_line = {
                        "stocktake_line_id": stocktake_line_id,
                        "stocktake_id": stocktake_id,
                        "item_id": r["item_id"],
                        "qty": str(r["stock_qty"]),
                        "stock_qty": str(r["stock_qty"]),
                        "unit_id": r["stock_unit"],
                        "stock_unit": r["stock_unit"],
                        "base_qty": str(round(stock_base_qty, 3)),
                        "base_unit": stock_base_unit,
                        "created_at": now,
                        "created_by": "SYSTEM",
                        "updated_at": "",
                        "updated_by": "",
                    }
                    for k, v in defaults_line.items():
                        if k in row_dict:
                            row_dict[k] = v
                    stock_line_rows.append(row_dict)

                append_rows_by_header("stocktake_lines", stl_header, stock_line_rows)

            po_id = ""
            if order_rows:
                po_header = get_header("purchase_orders")
                pol_header = get_header("purchase_order_lines")

                po_id = id_map["po_id"][0]

                po_row = {c: "" for c in po_header}
                defaults_po = {
                    "po_id": po_id,
                    "store_id": st.session_state.store_id,
                    "vendor_id": st.session_state.vendor_id,
                    "order_date": str(st.session_state.record_date),
                    "status": "draft",
                    "note": "",
                    "created_at": now,
                    "created_by": "SYSTEM",
                    "updated_at": "",
                    "updated_by": "",
                }
                for k, v in defaults_po.items():
                    if k in po_row:
                        po_row[k] = v

                append_rows_by_header("purchase_orders", po_header, [po_row])

                po_line_rows = []
                for idx, r in enumerate(order_rows):
                    po_line_id = id_map["po_line_id"][idx]

                    try:
                        order_base_qty, order_base_unit = convert_to_base(
                            item_id=r["item_id"],
                            qty=r["order_qty"],
                            from_unit=r["order_unit"],
                            items_df=vendor_items,
                            conversions_df=conversions_df,
                            as_of_date=st.session_state.record_date,
                        )
                    except Exception:
                        order_base_qty = r["order_qty"]
                        order_base_unit = r["order_unit"]

                    line_amount = round(float(r["order_qty"]) * float(r["unit_price"]), 1)

                    row_dict = {c: "" for c in pol_header}
                    defaults_pol = {
                        "po_line_id": po_line_id,
                        "po_id": po_id,
                        "item_id": r["item_id"],
                        "qty": str(r["order_qty"]),
                        "order_qty": str(r["order_qty"]),
                        "unit_id": r["order_unit"],
                        "order_unit": r["order_unit"],
                        "base_qty": str(round(order_base_qty, 3)),
                        "base_unit": order_base_unit,
                        "unit_price": str(r["unit_price"]),
                        "amount": str(line_amount),
                        "line_amount": str(line_amount),
                        "created_at": now,
                        "created_by": "SYSTEM",
                        "updated_at": "",
                        "updated_by": "",
                    }
                    for k, v in defaults_pol.items():
                        if k in row_dict:
                            row_dict[k] = v
                    po_line_rows.append(row_dict)

                append_rows_by_header("purchase_order_lines", pol_header, po_line_rows)

            bust_cache()
            st.success(f"✅ 已儲存；{('並建立叫貨單：' + po_id) if po_id else '本次無叫貨品項'}")
            st.session_state.step = "select_vendor"
            st.rerun()

        except Exception as e:
            st.error(f"❌ 儲存失敗：{e}")
            if st.button("⬅️ 返回功能選單", use_container_width=True, key="back_after_save_error"):
                st.session_state.step = "select_vendor"
                st.rerun()
            return

    if st.button("⬅️ 返回功能選單", use_container_width=True, key="back_from_order_entry"):
        st.session_state.step = "select_vendor"
        st.rerun()



