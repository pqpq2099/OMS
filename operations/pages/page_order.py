from __future__ import annotations

from datetime import date

import streamlit as st

from operations.logic import logic_order
from operations.logic.order_errors import SystemProcessError, UserDisplayError
from operations.logic.order_write import _save_order_entry
from pages.page_order_entry import (
    page_daily_stock_order_record as _legacy_page_daily_stock_order_record,
    page_order_message_detail as _legacy_page_order_message_detail,
)
from pages.page_order_entry import _fmt_qty_with_unit


WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"]
WEEKDAY_OPTIONS = [f"週{x}" for x in WEEKDAY_LABELS]


def page_select_store():
    st.markdown(
        "<style>.block-container { padding-top: 4rem !important; }</style>",
        unsafe_allow_html=True,
    )
    st.title("選擇門市")

    view_model = logic_order.get_store_selection_view_model()
    stores_df = view_model["stores_df"]

    if view_model["error_message"]:
        st.error(view_model["error_message"])
        return

    if stores_df.empty:
        st.warning("目前沒有可選門市資料。")
        return

    for _, row in stores_df.iterrows():
        label = row["store_label"]
        store_id = str(row.get("store_id", "")).strip()
        if st.button(f"進入 {label}", key=f"store_{store_id}", use_container_width=True):
            st.session_state.store_id = store_id
            st.session_state.store_name = label
            st.session_state.vendor_id = ""
            st.session_state.vendor_name = ""
            st.session_state.step = "select_vendor"
            st.rerun()


def page_select_vendor():
    st.markdown(
        "<style>.block-container { padding-top: 4rem !important; }</style>",
        unsafe_allow_html=True,
    )
    st.title(f"門市 {st.session_state.store_name}")

    selected_record_date = st.date_input(
        "作業日期",
        value=st.session_state.get("record_date", date.today()),
        key="select_vendor_record_date",
    )
    st.session_state.record_date = selected_record_date

    view_model = logic_order.get_vendor_selection_view_model(
        record_date=selected_record_date,
        store_id=st.session_state.get("store_id", ""),
    )
    vendors_df = view_model["vendors_df"]
    items_df = view_model["items_df"]
    vendors = view_model["vendors"]

    if vendors_df.empty or items_df.empty:
        st.warning("目前缺少廠商或品項資料。")
        return

    if vendors.empty:
        st.warning("目前沒有可選廠商。")
        return

    for i in range(0, len(vendors), 2):
        cols = st.columns(2)

        left = vendors.iloc[i]
        with cols[0]:
            if st.button(
                f"選擇 {left['vendor_label']}",
                key=f"vendor_{left.get('vendor_id', '')}",
                use_container_width=True,
            ):
                st.session_state.vendor_id = str(left.get("vendor_id", "")).strip()
                st.session_state.vendor_name = left["vendor_label"]
                st.session_state.step = "order_entry"
                st.rerun()

        if i + 1 < len(vendors):
            right = vendors.iloc[i + 1]
            with cols[1]:
                if st.button(
                    f"選擇 {right['vendor_label']}",
                    key=f"vendor_{right.get('vendor_id', '')}",
                    use_container_width=True,
                ):
                    st.session_state.vendor_id = str(right.get("vendor_id", "")).strip()
                    st.session_state.vendor_name = right["vendor_label"]
                    st.session_state.step = "order_entry"
                    st.rerun()

    st.write("<b>其他功能</b>", unsafe_allow_html=True)

    if st.button("查看 LINE 訊息明細", type="primary", use_container_width=True):
        st.session_state.step = "order_message_detail"
        st.rerun()

    if st.button("查看分析頁", use_container_width=True):
        st.session_state.step = "analysis"
        st.rerun()

    if st.button("查看每日盤點/叫貨紀錄", use_container_width=True):
        st.session_state.step = "view_history"
        st.rerun()

    if st.button("返回門市選擇", use_container_width=True):
        st.session_state.step = "select_store"
        st.rerun()


def page_order():
    view_model = logic_order.build_order_entry_view_model(
        store_id=st.session_state.store_id,
        vendor_id=st.session_state.vendor_id,
        record_date=st.session_state.record_date,
        weekday_options=WEEKDAY_OPTIONS,
    )

    if view_model["is_initial_stock"]:
        st.warning(
            "這是該門市的首次盤點。首次作業時，至少要輸入庫存或叫貨資料，避免建立空白資料。"
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

    st.title(f"叫貨 {st.session_state.vendor_name}")

    if view_model["items_df_empty"]:
        st.warning("目前沒有品項資料。")
        return

    if view_model["items_missing_default_vendor_id"]:
        st.warning("items 缺少 default_vendor_id 欄位。")
        return

    vendor_items = view_model["vendor_items"]
    if vendor_items.empty:
        st.info("目前該廠商沒有可叫貨品項。")
        if st.button("返回廠商選擇", use_container_width=True):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    existing_ids = view_model["existing_ids"]
    if view_model["is_edit_mode"]:
        st.info("目前為編輯模式，將沿用既有單據資料作為預設值。")
        edit_lines = [f"作業日期：{st.session_state.record_date}"]
        if existing_ids.get("stocktake_id"):
            edit_lines.append(f"盤點單：{existing_ids.get('stocktake_id')}")
        if existing_ids.get("po_id"):
            edit_lines.append(f"叫貨單：{existing_ids.get('po_id')}")
        if existing_ids.get("delivery_date"):
            edit_lines.append(f"到貨日：{existing_ids.get('delivery_date')}")
        st.caption(" / ".join(edit_lines))

    ref_df = view_model["ref_df"]
    with st.expander("上次叫貨量 / 近期待用量參考", expanded=False):
        if ref_df.empty:
            st.caption("目前沒有可參考資料。")
        else:
            display_df = ref_df.copy()
            display_df["上次叫貨量"] = display_df.apply(
                lambda row: _fmt_qty_with_unit(
                    row["last_order_display"],
                    row["last_order_unit"],
                ),
                axis=1,
            )
            display_df["近期待用量"] = display_df.apply(
                lambda row: _fmt_qty_with_unit(
                    row["period_usage_display"],
                    row["stock_unit"],
                ),
                axis=1,
            )
            st.table(display_df[["item_name", "上次叫貨量", "近期待用量"]].rename(columns={"item_name": "品項"}))

    st.markdown("<div class='order-divider'></div>", unsafe_allow_html=True)

    condition_col, stock_head_col, order_head_col = st.columns([6, 1, 1])
    with condition_col:
        st.write("**品項名稱 / 建議資訊**")
    with stock_head_col:
        st.write("<div style='text-align:center;'><b>庫存</b></div>", unsafe_allow_html=True)
    with order_head_col:
        st.write("<div style='text-align:center;'><b>叫貨</b></div>", unsafe_allow_html=True)

    conversions_df = view_model["conversions_df"]

    with st.form("order_entry_form"):
        submit_rows = []

        for _, row in vendor_items.iterrows():
            item_id = str(row.get("item_id", "")).strip()
            meta = view_model["item_meta"][item_id]

            c1, c2, c3 = st.columns([6, 1, 1])

            with c1:
                st.write(f"<b>{meta['item_name']}</b>", unsafe_allow_html=True)
                info_parts = [
                    f"上次叫貨 {_fmt_qty_with_unit(meta['last_order_display'], meta['order_unit'])}",
                    f"日平均 {meta['daily_avg']:g}{meta['stock_unit']}",
                    f"建議 {_fmt_qty_with_unit(meta['suggest_display'], meta['stock_unit'])}",
                ]
                if meta["status_hint"]:
                    info_parts.append(meta["status_hint"])
                st.markdown(
                    f"<div class='order-meta'>{' / '.join(info_parts)}</div>",
                    unsafe_allow_html=True,
                )

            with c2:
                stock_input = st.number_input(
                    "庫存",
                    min_value=0.0,
                    step=0.1,
                    format="%g",
                    value=float(meta["current_stock_qty"]),
                    key=f"stock_{item_id}",
                    label_visibility="collapsed",
                )
                st.markdown(
                    f"<div class='order-unit-label'>{meta['stock_unit']}</div>",
                    unsafe_allow_html=True,
                )

            with c3:
                order_input = st.number_input(
                    "叫貨",
                    min_value=0.0,
                    step=0.1,
                    format="%g",
                    value=float(meta["existing_order_qty"]),
                    key=f"order_{item_id}",
                    label_visibility="collapsed",
                )
                selected_order_unit = st.selectbox(
                    "叫貨單位",
                    options=meta["orderable_unit_options"],
                    index=meta["orderable_unit_options"].index(meta["existing_order_unit"])
                    if meta["existing_order_unit"] in meta["orderable_unit_options"]
                    else 0,
                    key=f"order_unit_{item_id}",
                    label_visibility="collapsed",
                )

            submit_rows.append(
                {
                    "item_id": item_id,
                    "item_name": meta["item_name"],
                    "stock_qty": float(stock_input),
                    "stock_unit": meta["stock_unit"],
                    "order_qty": float(order_input),
                    "order_unit": selected_order_unit,
                    "unit_price": float(meta["price"]),
                }
            )

        st.markdown("<div class='order-divider'></div>", unsafe_allow_html=True)

        default_delivery_index = (
            WEEKDAY_OPTIONS.index(view_model["existing_delivery_option"])
            if view_model["existing_delivery_option"] in WEEKDAY_OPTIONS
            else 0
        )
        selected_delivery_weekday = st.selectbox(
            "到貨星期",
            options=WEEKDAY_OPTIONS,
            index=default_delivery_index,
            key="delivery_weekday_option",
        )
        delivery_date = logic_order.delivery_date_from_weekday(
            st.session_state.record_date,
            selected_delivery_weekday,
            WEEKDAY_OPTIONS,
        )
        st.caption(
            f"預計到貨日期：{delivery_date.strftime('%Y-%m-%d')}（週{WEEKDAY_LABELS[delivery_date.weekday()]}）"
        )

        submitted = st.form_submit_button("提交叫貨", use_container_width=True)

        if submitted:
            errors = logic_order.validate_order_submission(
                submit_rows=submit_rows,
                vendor_items=vendor_items,
                conversions_df=conversions_df,
                record_date=st.session_state.record_date,
                is_initial_stock=view_model["is_initial_stock"],
            )

            if errors:
                for message in errors:
                    st.error(message)
                return

            try:
                po_id = _save_order_entry(
                    submit_rows=submit_rows,
                    vendor_items=vendor_items,
                    conversions_df=conversions_df,
                    store_id=st.session_state.store_id,
                    vendor_id=st.session_state.vendor_id,
                    record_date=st.session_state.record_date,
                    delivery_date=delivery_date,
                    existing_stocktake_id=existing_ids.get("stocktake_id", ""),
                    existing_po_id=existing_ids.get("po_id", ""),
                    is_initial_stock=view_model["is_initial_stock"],
                )

                action_text = "已更新叫貨資料" if view_model["is_edit_mode"] else "已建立叫貨資料"
                tail_text = f" / 叫貨單號 {po_id}" if po_id else ""
                st.success(f"{action_text}{tail_text}")
                st.session_state.step = "select_vendor"
                st.rerun()
            except Exception as exc:
                st.error(f"提交失敗：{exc}")
                return

    if st.button("返回廠商選擇", use_container_width=True, key="back_from_order"):
        st.session_state.step = "select_vendor"
        st.rerun()

def page_order_message_detail():
    return _legacy_page_order_message_detail()


def page_daily_stock_order_record():
    return _legacy_page_daily_stock_order_record()

