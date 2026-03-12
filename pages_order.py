from __future__ import annotations

# ============================================================
# [A1] 基本匯入
# 這一區放：日期、Streamlit、核心函式
# ============================================================
from datetime import date
import streamlit as st
import pandas as pd

from oms_core import (
    _build_latest_item_metrics_df,
    _build_stock_detail_df,
    _clean_option_list,
    _get_active_df,
    _get_last_po_summary,
    _get_latest_price_for_item,
    _get_latest_stock_qty_in_display_unit,
    _item_display_name,
    _label_store,
    _label_vendor,
    _norm,
    _now_ts,
    _safe_float,
    _sort_items_for_operation,
    _status_hint,
    allocate_ids,
    append_rows_by_header,
    bust_cache,
    get_header,
    read_table,
)
from oms_engine import convert_to_base


# ============================================================
# [B1] 盤點引擎輔助函式
# 這一區放：抓上一筆庫存、建立本次新庫存
# 規則：
# 1. 有輸入 → 用新值覆蓋
# 2. 未輸入 → 沿用上一筆
# ============================================================
def _get_last_stock_map_for_store(store_id: str) -> dict[str, float]:
    """
    取得某分店每個品項最後一次盤點的庫存（顯示單位）
    回傳格式：
    {
        "ITEM_001": 10.0,
        "ITEM_002": 5.0,
    }
    """
    stock_df = _build_stock_detail_df()
    if stock_df.empty:
        return {}

    work = stock_df[
        stock_df["store_id"].astype(str).str.strip() == str(store_id).strip()
    ].copy()

    if work.empty or "stocktake_date_dt" not in work.columns:
        return {}

    work = work[work["stocktake_date_dt"].notna()].copy()
    if work.empty:
        return {}

    work = work.sort_values(["stocktake_date_dt"], ascending=True)

    latest = (
        work.groupby("item_id", as_index=False)
        .tail(1)
        .copy()
    )

    result = {}
    for _, row in latest.iterrows():
        item_id = _norm(row.get("item_id", ""))
        qty = _safe_float(row.get("display_stock_qty", 0))
        if item_id:
            result[item_id] = qty

    return result


def _build_new_stock_map(
    last_stock_map: dict[str, float],
    current_input_map: dict[str, float],
) -> dict[str, float]:
    """
    規則：
    1. 先沿用上一筆庫存
    2. 本次有輸入的品項，用新值覆蓋
    3. 本次沒輸入的品項，沿用舊值
    """
    result = dict(last_stock_map or {})

    for item_id, qty in (current_input_map or {}).items():
        item_id = _norm(item_id)
        if not item_id:
            continue
        result[item_id] = _safe_float(qty, 0)

    return result


# ============================================================
# [E1] Select Store
# 這一區放：選擇分店頁
# ============================================================
def page_select_store():
    st.markdown(
        "<style>.block-container { padding-top: 4rem !important; }</style>",
        unsafe_allow_html=True,
    )
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
# 這一區放：選擇廠商頁
# ============================================================
def page_select_vendor():
    st.markdown(
        "<style>.block-container { padding-top: 4rem !important; }</style>",
        unsafe_allow_html=True,
    )
    st.title(f"🏢 {st.session_state.store_name}")

    st.session_state.record_date = st.date_input(
        "🗓️ 作業日期",
        value=st.session_state.record_date,
    )

    vendors_df = _get_active_df(read_table("vendors"))
    items_df = _get_active_df(read_table("items"))

    if vendors_df.empty or items_df.empty:
        st.warning("⚠️ 廠商或品項資料讀取失敗")
        return

    item_vendor_ids = set(items_df.get("default_vendor_id", []).astype(str).str.strip())
    vendors = vendors_df[
        vendors_df["vendor_id"].astype(str).str.strip().isin(item_vendor_ids)
    ].copy()

    if vendors.empty:
        st.warning("⚠️ 目前沒有可用廠商")
        return

    vendors["vendor_label"] = vendors.apply(_label_vendor, axis=1)
    vendors = vendors.sort_values(by=["vendor_label"], ascending=True).reset_index(drop=True)

    for i in range(0, len(vendors), 2):
        cols = st.columns(2)

        left = vendors.iloc[i]
        with cols[0]:
            if st.button(
                f"📦 {left['vendor_label']}",
                key=f"vendor_{left.get('vendor_id', '')}",
                use_container_width=True,
            ):
                st.session_state.vendor_id = _norm(left.get("vendor_id", ""))
                st.session_state.vendor_name = left["vendor_label"]
                st.session_state.step = "order_entry"
                st.rerun()

        if i + 1 < len(vendors):
            right = vendors.iloc[i + 1]
            with cols[1]:
                if st.button(
                    f"📦 {right['vendor_label']}",
                    key=f"vendor_{right.get('vendor_id', '')}",
                    use_container_width=True,
                ):
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

    if st.button("📜 查看分店歷史紀錄", use_container_width=True):
        st.session_state.step = "view_history"
        st.rerun()

    if st.button("⬅️ 返回分店列表", use_container_width=True):
        st.session_state.step = "select_store"
        st.rerun()


# ============================================================
# [E3] Order Entry
# 這一區放：盤點 / 叫貨主頁
# 說明：
# 庫 = 盤點庫存
# 進 = 叫貨數量
# ============================================================
def page_order_entry():
    # ============================================================
    # 初始化庫存判斷
    # 若此分店還沒有任何 stocktake 紀錄，這次視為初始化
    # ============================================================
    stocktakes_df = read_table("stocktakes")

    if stocktakes_df.empty or "store_id" not in stocktakes_df.columns:
        is_initial_stock = True
    else:
        store_stocktakes = stocktakes_df[
            stocktakes_df["store_id"].astype(str).str.strip() == str(st.session_state.store_id).strip()
        ]
        is_initial_stock = len(store_stocktakes) == 0

    if is_initial_stock:
        st.warning(
            "⚠️ 目前尚無庫存基準資料，本次儲存將建立「初始化庫存」。"
            "請先填寫目前實際庫存；未來再依正常流程盤點 / 叫貨。"
        )

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
            color: rgba(170, 178, 195, 0.9);
            margin-top: -0.2rem;
            margin-bottom: 0.25rem;
        }

        .order-unit-label {
            display: flex;
            align-items: flex-end;
            justify-content: center;
            height: 34px;
            font-size: 1rem;
            font-weight: 500;
            opacity: 0.9;
            margin-top: 3px;
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
        items_df["default_vendor_id"].astype(str).str.strip()
        == str(st.session_state.vendor_id).strip()
    ].copy()

    if vendor_items.empty:
        st.info("💡 此廠商目前沒有對應品項")
        if st.button("⬅️ 返回功能選單", use_container_width=True):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    vendor_items = vendor_items.reset_index(drop=True)

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

        price = _get_latest_price_for_item(
            prices_df,
            item_id,
            st.session_state.record_date,
        )

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
            stock_unit = meta["stock_unit"]
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
                f"<div class='order-meta'>總庫存：{total_stock_ref:g}　建議量：{suggest_qty:g}{tail}</div>",
                unsafe_allow_html=True,
            )
            with c2:
                stock_input = st.number_input(
                    "庫",
                    min_value=0,
                    step=1,
                    format="%d",
                    value=0,
                    key=f"stock_{item_id}",
                    label_visibility="collapsed",
                )
                st.markdown(
                    f"<div class='order-unit-label'>{stock_unit}</div>",
                    unsafe_allow_html=True,
                )

            with c3:
                order_input = st.number_input(
                    "進",
                    min_value=0.0,
                    step=0.1,
                    format="%g",
                    value=0.0,
                    key=f"order_{item_id}",
                    label_visibility="collapsed",
                )
                selected_order_unit = st.selectbox(
                    "進貨單位",
                    options=meta["orderable_unit_options"],
                    index=meta["orderable_unit_options"].index(order_unit)
                    if order_unit in meta["orderable_unit_options"]
                    else 0,
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

        submitted = st.form_submit_button("💾 儲存並同步", use_container_width=True)

    if submitted:
        try:
            po_id = _save_order_entry(
                submit_rows=submit_rows,
                vendor_items=vendor_items,
                conversions_df=conversions_df,
                store_id=st.session_state.store_id,
                vendor_id=st.session_state.vendor_id,
                record_date=st.session_state.record_date,
                is_initial_stock=is_initial_stock,
            )

            st.success(
                f"✅ 已儲存；{('並建立叫貨單：' + po_id) if po_id else '本次無叫貨品項'}"
            )
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


# ============================================================
# [E4] Save Order Entry
# 這一區放：儲存盤點 / 叫貨
# 修正重點：
# 1. 庫存不是只存 >0，而是依照「上一筆 + 本次覆蓋」建立新盤點
# 2. 未輸入的品項沿用上一筆
# 3. 初始化時，這一頁的庫存就是第一筆基準庫存
# ============================================================
def _save_order_entry(
    submit_rows,
    vendor_items,
    conversions_df,
    store_id,
    vendor_id,
    record_date,
    is_initial_stock: bool,
):
    now = _now_ts()

    # ============================================================
    # 1. 叫貨資料：只保留 > 0 的列
    # ============================================================
    order_rows = [r for r in submit_rows if _safe_float(r["order_qty"]) > 0]

    # ============================================================
    # 2. 盤點資料：
    #    使用「上一筆庫存 + 本次輸入覆蓋」方式建立完整新盤點
    # ============================================================
    last_stock_map = _get_last_stock_map_for_store(store_id=store_id)

    current_input_map = {
        _norm(r["item_id"]): (
            None if _safe_float(r["stock_qty"]) == 0
            else _safe_float(r["stock_qty"])
        )
        for r in submit_rows
    }

    new_stock_map = _build_new_stock_map(
        last_stock_map=last_stock_map,
        current_input_map=current_input_map,
    )

    # 只保留本次畫面裡屬於該廠商的品項
    vendor_item_ids = set(vendor_items["item_id"].astype(str).str.strip())
    new_stock_map = {
        item_id: qty
        for item_id, qty in new_stock_map.items()
        if item_id in vendor_item_ids
    }

    stocktake_rows = []
    for _, row in vendor_items.iterrows():
        item_id = _norm(row.get("item_id", ""))
        if item_id not in new_stock_map:
            continue

        meta_row = next((r for r in submit_rows if _norm(r["item_id"]) == item_id), None)
        stock_unit = _norm(row.get("default_stock_unit", "")) or _norm(row.get("base_unit", ""))
        stock_qty = _safe_float(new_stock_map.get(item_id, 0))

        stocktake_rows.append(
            {
                "item_id": item_id,
                "item_name": _item_display_name(row),
                "stock_qty": stock_qty,
                "stock_unit": meta_row["stock_unit"] if meta_row else stock_unit,
            }
        )

    # ============================================================
    # 3. 申請 ID
    # ============================================================
    id_need = {
        "stocktake_id": 1 if stocktake_rows else 0,
        "stocktake_line_id": len(stocktake_rows),
        "po_id": 1 if order_rows else 0,
        "po_line_id": len(order_rows),
    }
    id_map = allocate_ids(id_need)

    # ============================================================
    # 4. 寫入 stocktakes / stocktake_lines
    # ============================================================
    if stocktake_rows:
        stocktake_header = get_header("stocktakes")
        stl_header = get_header("stocktake_lines")

        stocktake_id = id_map["stocktake_id"][0]
        stocktake_main_row = {c: "" for c in stocktake_header}

        defaults = {
            "stocktake_id": stocktake_id,
            "store_id": store_id,
            "stocktake_date": str(record_date),
            "stocktake_type": "initial" if is_initial_stock else "regular",
            "status": "done",
            "note": "initial_stock" if is_initial_stock else f"vendor={vendor_id}",
            "created_at": now,
            "created_by": "SYSTEM",
        }

        for k, v in defaults.items():
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
                    as_of_date=record_date,
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
            }

            for k, v in defaults_line.items():
                if k in row_dict:
                    row_dict[k] = v

            stock_line_rows.append(row_dict)

        append_rows_by_header("stocktake_lines", stl_header, stock_line_rows)

    # ============================================================
    # 5. 寫入 purchase_orders / purchase_order_lines
    # ============================================================
    po_id = ""

    if order_rows:
        po_header = get_header("purchase_orders")
        pol_header = get_header("purchase_order_lines")

        po_id = id_map["po_id"][0]
        po_row = {c: "" for c in po_header}

        defaults_po = {
            "po_id": po_id,
            "store_id": store_id,
            "vendor_id": vendor_id,
            "order_date": str(record_date),
            "delivery_date": str(record_date),  # 先保守不亂加一天，避免跟你現有表頭/流程衝突
            "status": "draft",
            "created_at": now,
            "created_by": "SYSTEM",
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
                    as_of_date=record_date,
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
            }

            for k, v in defaults_pol.items():
                if k in row_dict:
                    row_dict[k] = v

            po_line_rows.append(row_dict)

        append_rows_by_header("purchase_order_lines", pol_header, po_line_rows)

    bust_cache()
    return po_id

# ============================================================
# [E5] Order Message Detail
# 這一區放：叫貨明細（LINE格式顯示）
# 功能：
# 1. 選擇單日日期
# 2. 顯示當天叫貨內容
# 3. 顯示方式與LINE通知一致
# ============================================================
def page_order_message_detail():
    st.title("🧾 叫貨明細")

    # ========================================================
    # 1. 先確認目前分店
    # ========================================================
    store_id = st.session_state.get("store_id", "")
    store_name = st.session_state.get("store_name", "")

    if not store_id:
        st.warning("請先選擇分店")
        return

    # ========================================================
    # 2. 選擇日期（單日）
    # ========================================================
    selected_date = st.date_input(
        "日期",
        value=date.today(),
        key="order_message_detail_date",
    )

    # ========================================================
    # 3. 讀取資料
    # ========================================================
    po_df = read_table("purchase_orders")
    pol_df = read_table("purchase_order_lines")
    vendors_df = read_table("vendors")
    items_df = read_table("items")

    if po_df.empty or pol_df.empty:
        st.info("目前沒有叫貨資料")
        return

    # ========================================================
    # 4. 日期格式整理
    # ========================================================
    if "order_date" not in po_df.columns:
        st.error("purchase_orders 缺少 order_date 欄位")
        return

    po_df = po_df.copy()
    po_df["order_date"] = pd.to_datetime(po_df["order_date"], errors="coerce").dt.date

    # ========================================================
    # 5. 篩出指定分店＋指定日期的主單
    # ========================================================
    if "store_id" not in po_df.columns or "po_id" not in po_df.columns:
        st.error("purchase_orders 缺少 store_id 或 po_id 欄位")
        return

    po_today = po_df[
        (po_df["store_id"].astype(str) == str(store_id))
        & (po_df["order_date"] == selected_date)
    ].copy()

    if po_today.empty:
        st.info("這一天沒有叫貨紀錄")
        return

    # ========================================================
    # 6. 篩出明細
    # ========================================================
    if "po_id" not in pol_df.columns:
        st.error("purchase_order_lines 缺少 po_id 欄位")
        return

    po_ids = po_today["po_id"].astype(str).tolist()

    pol_df = pol_df.copy()
    pol_df["po_id"] = pol_df["po_id"].astype(str)

    lines_today = pol_df[pol_df["po_id"].isin(po_ids)].copy()

    if lines_today.empty:
        st.info("這一天沒有叫貨明細")
        return

    # ========================================================
    # 7. 建立廠商名稱對照
    #    顯示優先沿用系統既有規則
    # ========================================================
    vendor_map = dict(
        zip(
            vendors_df["vendor_id"].astype(str),
            vendors_df["vendor_name_zh"].fillna("").astype(str),
        )
    )
    # ========================================================
    # 8. 建立品項名稱對照
    #    顯示優先：item_name_zh > item_name > item_id
    # ========================================================
    item_name_col = None
    if "item_name_zh" in items_df.columns:
        item_name_col = "item_name_zh"
    elif "item_name" in items_df.columns:
        item_name_col = "item_name"

    item_map = {}
    if "item_id" in items_df.columns:
        for _, r in items_df.iterrows():
            iid = str(r.get("item_id", ""))
            display_name = ""
            if item_name_col:
                display_name = str(r.get(item_name_col, "")).strip()
            if not display_name:
                display_name = iid
            item_map[iid] = display_name

    # ========================================================
    # 9. 合併主單與明細
    # ========================================================
    po_today["po_id"] = po_today["po_id"].astype(str)

    merged = lines_today.merge(
        po_today[["po_id", "vendor_id"]],
        on="po_id",
        how="left",
        suffixes=("", "_po"),
    )

    # 找實際可用的 vendor_id 欄位
    vendor_id_col = None
    if "vendor_id_po" in merged.columns:
        vendor_id_col = "vendor_id_po"
    elif "vendor_id_y" in merged.columns:
        vendor_id_col = "vendor_id_y"
    elif "vendor_id" in merged.columns:
        vendor_id_col = "vendor_id"
    elif "vendor_id_x" in merged.columns:
        vendor_id_col = "vendor_id_x"

    if vendor_id_col is None:
        st.error("合併後找不到 vendor_id 欄位")
        return

    merged["vendor_name"] = (
        merged[vendor_id_col].astype(str).str.strip().map(vendor_map).fillna("未分類廠商")
    )
    merged["item_name"] = (
        merged["item_id"].astype(str).map(item_map).fillna(merged["item_id"].astype(str))
    )
    # ========================================================
    # 10. 抓數量 / 單位欄位
    # ========================================================
    qty_col = "order_qty" if "order_qty" in merged.columns else "qty"
    unit_col = "order_unit" if "order_unit" in merged.columns else "unit_id"

    if qty_col not in merged.columns:
        st.error("purchase_order_lines 缺少 order_qty / qty 欄位")
        return

    if unit_col not in merged.columns:
        st.error("purchase_order_lines 缺少 order_unit / unit_id 欄位")
        return

    # ========================================================
    # 11. 數量格式整理
    # ========================================================
    def _fmt_qty(v):
        try:
            v = float(v)
            if v.is_integer():
                return str(int(v))
            return f"{v:.1f}"
        except Exception:
            return str(v)

    # ========================================================
    # 12. 產生 LINE 訊息內容
    # ========================================================
    lines = []
    lines.append("今日進貨明細")

    if store_name:
        lines.append(store_name)

    lines.append(str(selected_date))
    lines.append("")

    for vendor_name, group in merged.groupby("vendor_name", sort=False):
        show_vendor = vendor_name.strip() if str(vendor_name).strip() else "未分類廠商"
        lines.append(show_vendor)

        for _, r in group.iterrows():
            item_name = str(r.get("item_name", "")).strip()
            qty = _fmt_qty(r.get(qty_col, ""))
            unit = str(r.get(unit_col, "")).strip()
            lines.append(f"{item_name} {qty}{unit}")

        lines.append("")

    line_message = "\n".join(lines).strip()

    # ========================================================
    # 13. 顯示
    # ========================================================
    st.markdown("### LINE 顯示內容")
    st.code(line_message, language="text")










