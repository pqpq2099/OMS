from __future__ import annotations

from datetime import date

import streamlit as st

from shared.core.navigation import goto
from operations.logic import logic_order
from operations.logic.order_errors import SystemProcessError, UserDisplayError
from shared.utils.utils_format import _fmt_qty_with_unit, unit_label
from shared.utils.permissions import filter_stores_by_scope, require_permission, has_permission


WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"]
WEEKDAY_OPTIONS = [f"星期{x}" for x in WEEKDAY_LABELS]


def page_select_store():
    st.markdown(
        "<style>.block-container { padding-top: 4rem !important; }</style>",
        unsafe_allow_html=True,
    )
    st.title("🏠 選擇分店")

    view_model = logic_order.get_store_selection_view_model()
    stores_df = filter_stores_by_scope(view_model["stores_df"])

    if view_model["error_message"]:
        st.error(view_model["error_message"])
        return

    if stores_df.empty:
        st.warning("目前沒有可選分店資料。")
        return

    for _, row in stores_df.iterrows():
        label = row["store_label"]
        store_id = str(row.get("store_id", "")).strip()
        if st.button(f"📍 {label}", key=f"store_{store_id}", use_container_width=True):
            st.session_state.store_id = store_id
            st.session_state.store_name = label
            st.session_state.vendor_id = ""
            st.session_state.vendor_name = ""
            goto("select_vendor")


def page_select_vendor():
    st.markdown(
        "<style>.block-container { padding-top: 4rem !important; }</style>",
        unsafe_allow_html=True,
    )
    st.title(f"🏢 {st.session_state.store_name}")

    selected_record_date = st.date_input(
        "📅 作業日期",
        value=st.session_state.get("record_date", date.today()),
        key="select_vendor_record_date",
    )
    st.session_state.record_date = selected_record_date

    with st.spinner("載入中..."):
        view_model = logic_order.get_vendor_selection_view_model(
            record_date=selected_record_date,
            store_id=st.session_state.get("store_id", ""),
        )
    vendors_df = view_model["vendors_df"]
    items_df = view_model["items_df"]
    vendors = view_model["vendors"]

    if vendors_df.empty or items_df.empty:
        st.warning("目前缺少廠商或品項資料。請確認品項與廠商資料已建立。")
        return

    if vendors.empty:
        st.warning("此日期查無可叫貨廠商。請確認品項已設定預設廠商，或嘗試其他日期。")
        return

    for i in range(0, len(vendors), 2):
        cols = st.columns(2)

        left = vendors.iloc[i]
        with cols[0]:
            if st.button(
                f"📦 {left['vendor_label']}",
                key=f"vendor_{left.get('vendor_id', '')}",
                use_container_width=True,
            ):
                st.session_state.vendor_id = str(left.get("vendor_id", "")).strip()
                st.session_state.vendor_name = left["vendor_label"]
                goto("order_entry")

        if i + 1 < len(vendors):
            right = vendors.iloc[i + 1]
            with cols[1]:
                if st.button(
                    f"📦 {right['vendor_label']}",
                    key=f"vendor_{right.get('vendor_id', '')}",
                    use_container_width=True,
                ):
                    st.session_state.vendor_id = str(right.get("vendor_id", "")).strip()
                    st.session_state.vendor_name = right["vendor_label"]
                    goto("order_entry")

    st.write("<b>📊 報表與分析中心</b>", unsafe_allow_html=True)

    if st.button("📄 產生今日進貨明細", type="primary", use_container_width=True):
        goto("order_message_detail")

    if st.button("⬅️ 返回分店列表", use_container_width=True):
        goto("select_store")


def page_order():
    if not require_permission("operation.order.create"):
        return
    with st.spinner("載入中..."):
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

        .suggest-text {
            font-weight: 700;
        }

        .suggest-red {
            color: #e74c3c;
        }

        .suggest-yellow {
            color: #d4a017;
        }

        .suggest-green {
            color: #27ae60;
        }

        .price-text {
    opacity: 0.72;
    font-size: 0.8rem;
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

        .item-card {
            padding: 10px 12px;
            border-radius: 8px;
            margin-bottom: 6px;
            border-left: 5px solid transparent;
        }

        .priority-red {
    background-color: rgba(231, 76, 60, 0.05);
    border-left: 5px solid #e74c3c;
}

        .priority-yellow {
    background-color: rgba(241, 196, 15, 0.06);
    border-left: 5px solid #f1c40f;
}

        .priority-green {
    background-color: rgba(39, 174, 96, 0.05);
    border-left: 5px solid #27ae60;
}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title(f"📝 {st.session_state.vendor_name}")

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
            goto("select_vendor")
        return

    existing_ids = view_model["existing_ids"]
    if view_model["is_edit_mode"]:
        st.warning("這一天此廠商已有紀錄，畫面已自動帶入，按下儲存會直接覆寫更新。")
        st.caption(logic_order.build_order_edit_caption(existing_ids, st.session_state.record_date))

    st.markdown("<div class='order-divider'></div>", unsafe_allow_html=True)

    condition_col, stock_head_col, order_head_col = st.columns([6, 1, 1])
    with condition_col:
        st.write("**品項名稱（建議量=日均×1.5）**")
    with stock_head_col:
        st.write("<div style='text-align:center; font-size:0.75rem;'><b>本次庫存</b></div>", unsafe_allow_html=True)
    with order_head_col:
        st.write("<div style='text-align:center; font-size:0.75rem;'><b>本次叫貨</b></div>", unsafe_allow_html=True)

    conversions_df = view_model["conversions_df"]
    item_cards = logic_order.build_order_item_cards_view_model(
        vendor_items,
        view_model["item_meta"],
        _fmt_qty_with_unit,
    )

    with st.form("order_entry_form"):
        submit_rows = []

        for card in item_cards:
            item_id = card["item_id"]

            st.markdown(f'<div class="item-card {card["priority_class"]}">', unsafe_allow_html=True)

            c1, c2, c3 = st.columns([6, 1, 1])

            with c1:
                st.write(f"<b>{card['item_name']}</b>", unsafe_allow_html=True)
                st.markdown(
                    f"<div class='order-meta'>{card['info_html']}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<div class='order-meta'>{card['coverage_text']}</div>",
                    unsafe_allow_html=True,
                )

            with c2:
                stock_input = st.number_input(
                    "庫",
                    min_value=0.0,
                    step=0.1,
                    format="%g",
                    value=card["current_stock_qty"],
                    key=f"stock_{item_id}",
                    label_visibility="collapsed",
                )
                st.markdown(
                    f"<div class='order-unit-label'>{unit_label(card['stock_unit'])}</div>",
                    unsafe_allow_html=True,
                )

            with c3:
                order_input = st.number_input(
                    "進",
                    min_value=0.0,
                    step=0.1,
                    format="%g",
                    value=card["existing_order_qty"],
                    key=f"order_{item_id}",
                    label_visibility="collapsed",
                )
                selected_order_unit = st.selectbox(
                    "進貨單位",
                    options=card["orderable_unit_options"],
                    index=card["orderable_unit_options"].index(card["existing_order_unit"])
                    if card["existing_order_unit"] in card["orderable_unit_options"]
                    else 0,
                    format_func=unit_label,
                    key=f"order_unit_{item_id}",
                    label_visibility="collapsed",
                )

            st.markdown("</div>", unsafe_allow_html=True)

            submit_rows.append(
                {
                    "item_id": item_id,
                    "item_name": card["item_name"],
                    "stock_qty": float(stock_input),
                    "stock_unit": card["stock_unit"],
                    "order_qty": float(order_input),
                    "order_unit": selected_order_unit,
                    "unit_price": card["price"],
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
            f"本次到貨日：{delivery_date.strftime('%Y-%m-%d')}（{WEEKDAY_OPTIONS[delivery_date.weekday()]}）"
        )

        submitted = st.form_submit_button("💾 儲存並同步", use_container_width=True)

        if submitted:
            if not has_permission("operation.order.edit"):
                st.warning("⚠️ 您沒有提交叫貨的權限")
                return
            try:
                submit_result = logic_order.submit_order_entry(
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

                if not submit_result["ok"]:
                    for message in submit_result["errors"]:
                        st.error(message)
                    return

                po_id = submit_result["po_id"]
                action_text = "已更新叫貨資料" if view_model["is_edit_mode"] else "已建立叫貨資料"
                tail_text = f" / 叫貨單號 {po_id}" if po_id else ""
                st.success(f"{action_text}{tail_text}")
                goto("select_vendor")
            except UserDisplayError as exc:
                st.error(str(exc))
                return
            except SystemProcessError as exc:
                st.error(str(exc))
                return
            except Exception as exc:
                st.error(f"提交失敗：{exc}")
                return

    if st.button("⬅️ 返回功能選單", use_container_width=True, key="back_from_order"):
        goto("select_vendor")


