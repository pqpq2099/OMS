from __future__ import annotations

# ============================================================
# ORIVIA OMS
# 檔案：operations/pages/page_transfer.py
# 說明：調貨頁面
# 流程：選出貨店↔收貨店 → 品項表格（填調貨量）→ 確認彈窗 → 寫入
# 權限：operation.transfer.execute（leader+）
# 注意：跨店操作需同時驗證兩店在使用者的 store_scope 內
# ============================================================

from datetime import date

import streamlit as st

from shared.utils.permissions import require_permission, has_store_access
from shared.utils.utils_units import convert_to_base
from shared.utils.utils_format import unit_label
from shared.services.data_backend import read_table, bust_cache
from operations.logic.logic_transfer import (
    load_stores_for_transfer,
    load_items_for_transfer,
    save_transfer,
)


def page_transfer():
    st.markdown(
        "<style>.block-container { padding-top: 4rem !important; }</style>",
        unsafe_allow_html=True,
    )
    st.title("🔄 調貨")

    # ── 權限守衛 ──────────────────────────────────────────────
    if not require_permission("operation.transfer.execute", "調貨需要組長以上權限"):
        return

    # ── 作業日期 ──────────────────────────────────────────────
    transfer_date: date = st.date_input(
        "📅 調貨日期",
        value=st.session_state.get("record_date", date.today()),
        key="transfer_date",
    )

    # ── 分店選擇 ──────────────────────────────────────────────
    stores = load_stores_for_transfer()
    if len(stores) < 2:
        st.warning("目前可存取的分店不足 2 間，無法進行調貨。")
        return

    store_options = {s["store_name"]: s["store_id"] for s in stores}
    store_names = list(store_options.keys())

    col1, col2 = st.columns(2)
    with col1:
        from_name = st.selectbox("📤 出貨店", options=store_names, key="transfer_from_store")
    with col2:
        to_options = [n for n in store_names if n != from_name]
        to_name = st.selectbox("📥 收貨店", options=to_options, key="transfer_to_store")

    from_store_id = store_options[from_name]
    to_store_id = store_options.get(to_name, "")

    if not to_store_id or from_store_id == to_store_id:
        st.warning("出貨店與收貨店不可相同。")
        return

    # ── 跨店 scope 驗證 ───────────────────────────────────────
    if not has_store_access(from_store_id):
        st.error(f"您無權存取出貨店（{from_store_id}）。")
        return
    if not has_store_access(to_store_id):
        st.error(f"您無權存取收貨店（{to_store_id}）。")
        return

    # ── 載入出貨店品項 ────────────────────────────────────────
    cache_key = f"_transfer_items_{from_store_id}_{transfer_date.isoformat()}"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = load_items_for_transfer(from_store_id, transfer_date)

    items = st.session_state[cache_key]

    if not items:
        st.info(f"出貨店【{from_name}】目前無可調撥庫存品項（庫存皆為 0）。")
        return

    st.markdown("---")
    st.markdown("#### 品項調貨數量")
    st.caption("填寫調撥數量（0 = 不調貨）；調撥量不可超過出貨店現有庫存。")

    # ── 調貨數量輸入 ──────────────────────────────────────────
    qty_state_key = f"_transfer_qty_{from_store_id}_{to_store_id}_{transfer_date.isoformat()}"
    if qty_state_key not in st.session_state:
        st.session_state[qty_state_key] = {item["item_id"]: 0.0 for item in items}
    qty_map: dict = st.session_state[qty_state_key]

    for item in items:
        item_id = item["item_id"]
        unit_name = unit_label(item["display_unit"])
        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown(f"**{item['item_name']}**")
            st.caption(f"現有庫存：{item['current_display_qty']:g} {unit_name}")
        with col2:
            max_val = float(item["current_display_qty"])
            qty_val = st.number_input(
                f"調貨量（{unit_name}）",
                min_value=0.0,
                max_value=max_val,
                value=float(qty_map.get(item_id, 0.0)),
                step=0.1,
                format="%g",
                key=f"transfer_qty_{item_id}",
                label_visibility="collapsed",
            )
            qty_map[item_id] = qty_val

    # ── 計算調貨清單 ──────────────────────────────────────────
    transfer_items = []
    conversions_df = read_table("unit_conversions")
    items_df = read_table("items")

    for item in items:
        item_id = item["item_id"]
        transfer_disp = round(float(qty_map.get(item_id, 0.0)), 4)
        if transfer_disp <= 0:
            continue

        display_unit = item["display_unit"]
        base_unit = item["base_unit"]

        try:
            if display_unit == base_unit or not display_unit:
                transfer_base = transfer_disp
            else:
                transfer_base, _ = convert_to_base(
                    item_id=item_id,
                    qty=transfer_disp,
                    from_unit=display_unit,
                    items_df=items_df,
                    conversions_df=conversions_df,
                    as_of_date=transfer_date,
                )
        except Exception:
            transfer_base = transfer_disp

        transfer_items.append({
            "item_id": item_id,
            "item_name": item["item_name"],
            "vendor_id": item["vendor_id"],
            "transfer_display_qty": transfer_disp,
            "display_unit": display_unit,
            "transfer_base_qty": round(transfer_base, 4),
            "base_unit": base_unit,
            "current_base_qty": item["current_base_qty"],
            "current_display_qty": item["current_display_qty"],
        })

    # ── 確認提交 ──────────────────────────────────────────────
    st.markdown("---")
    if transfer_items:
        st.info(f"共 {len(transfer_items)} 個品項待調撥")
    else:
        st.caption("目前無品項填寫調貨數量。")

    if st.button("✅ 確認調貨", disabled=(not transfer_items), use_container_width=True):
        _show_confirm_dialog(from_store_id, from_name, to_store_id, to_name, transfer_date, transfer_items)


@st.dialog("確認調貨")
def _show_confirm_dialog(
    from_store_id: str,
    from_name: str,
    to_store_id: str,
    to_name: str,
    transfer_date: date,
    transfer_items: list[dict],
):
    """確認彈窗：顯示調貨摘要並寫入。"""
    st.markdown(f"**調貨日期**：{transfer_date.isoformat()}")
    st.markdown(f"**出貨店**：{from_name}")
    st.markdown(f"**收貨店**：{to_name}")
    st.markdown(f"**調撥品項**：{len(transfer_items)} 個")
    st.markdown("---")

    for item in transfer_items:
        uname = unit_label(item["display_unit"])
        st.write(
            f"• {item['item_name']}：{item['transfer_display_qty']:g} {uname}"
        )

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 確認送出", use_container_width=True, key="transfer_confirm_ok"):
            actor = str(st.session_state.get("login_user", "unknown")).strip()
            success, msg = save_transfer(
                from_store_id=from_store_id,
                to_store_id=to_store_id,
                transfer_date=transfer_date,
                actor=actor,
                items_to_transfer=transfer_items,
            )
            if success:
                # 清除快取
                for key in list(st.session_state.keys()):
                    if key.startswith("_transfer_"):
                        del st.session_state[key]
                bust_cache(["stocktakes", "stocktake_lines", "stock_transfers", "stock_transfer_lines"])
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    with col2:
        if st.button("✖ 取消", use_container_width=True, key="transfer_confirm_cancel"):
            st.rerun()
