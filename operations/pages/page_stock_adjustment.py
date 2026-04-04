from __future__ import annotations

# ============================================================
# ORIVIA OMS
# 檔案：operations/pages/page_stock_adjustment.py
# 說明：庫存調整頁面
# 流程：選擇廠商 → 品項表格（調整數量）→ 確認彈窗 → 寫入
# 權限：operation.stock.adjust（store_manager+）
# ============================================================

from datetime import date

import streamlit as st

from shared.utils.permissions import require_permission
from shared.utils.utils_units import convert_to_base
from shared.utils.utils_format import unit_label
from shared.services.data_backend import read_table, bust_cache
from operations.logic.logic_stock_adjustment import (
    load_vendors_for_store,
    load_items_for_adjustment,
    save_adjustment,
)


def page_stock_adjustment():
    st.markdown(
        "<style>.block-container { padding-top: 4rem !important; }</style>",
        unsafe_allow_html=True,
    )
    st.title("🔧 庫存調整")

    # ── 權限守衛 ──────────────────────────────────────────────
    if not require_permission("operation.stock.adjust", "庫存調整需要店長以上權限"):
        return

    # ── 分店確認 ──────────────────────────────────────────────
    store_id = str(st.session_state.get("store_id", "")).strip()
    store_name = str(st.session_state.get("store_name", "")).strip()
    if not store_id:
        st.warning("請先從作業區選擇分店。")
        return

    st.caption(f"📍 分店：{store_name or store_id}")

    # ── 作業日期 ──────────────────────────────────────────────
    adj_date: date = st.date_input(
        "📅 調整日期",
        value=st.session_state.get("record_date", date.today()),
        key="stock_adj_date",
    )

    # ── 廠商選擇 ──────────────────────────────────────────────
    vendors = load_vendors_for_store(store_id, adj_date)
    if not vendors:
        st.info("此分店目前無廠商庫存記錄。")
        return

    vendor_options = {v["vendor_name"]: v["vendor_id"] for v in vendors}
    vendor_name_selected = st.selectbox(
        "🏭 選擇廠商",
        options=list(vendor_options.keys()),
        key="stock_adj_vendor",
    )
    vendor_id_selected = vendor_options[vendor_name_selected]

    # ── 載入品項（廠商 + 日期 + 分店 任一變動時重載）──────────
    cache_key = f"_stock_adj_items_{store_id}_{vendor_id_selected}_{adj_date.isoformat()}"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = load_items_for_adjustment(store_id, vendor_id_selected, adj_date)

    items = st.session_state[cache_key]

    if not items:
        st.info(f"【{vendor_name_selected}】在此分店目前無可調整庫存品項（庫存皆為 0）。")
        return

    st.markdown("---")
    st.markdown("#### 品項庫存調整")
    st.caption("請輸入調整後的數量，與原數量相同的品項將不會寫入。")

    # 限制數字輸入欄位寬度（手機優化）
    st.markdown(
        """
        <style>
        div[data-testid="stNumberInputContainer"] {
            max-width: 120px !important;
            min-width: 100px !important;
        }
        div[data-testid="column"]:last-child {
            display: flex !important;
            align-items: center !important;
            justify-content: flex-end !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── 品項表格 ──────────────────────────────────────────────
    adj_state_key = f"_stock_adj_new_qty_{store_id}_{vendor_id_selected}_{adj_date.isoformat()}"
    if adj_state_key not in st.session_state:
        st.session_state[adj_state_key] = {
            item["item_id"]: item["current_display_qty"] for item in items
        }
    new_qty_map: dict = st.session_state[adj_state_key]

    for item in items:
        item_id = item["item_id"]
        unit_name = unit_label(item["display_unit"])
        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown(f"**{item['item_name']}**")
            st.caption(f"目前庫存：{item['current_display_qty']:g} {unit_name}")
        with col2:
            new_val = st.number_input(
                f"調整後數量（{unit_name}）",
                min_value=0.0,
                value=float(new_qty_map.get(item_id, item["current_display_qty"])),
                step=0.1,
                format="%g",
                key=f"adj_qty_{item_id}",
                label_visibility="collapsed",
            )
            new_qty_map[item_id] = new_val

    # ── 計算差異品項 ──────────────────────────────────────────
    changed_items = []
    conversions_df = read_table("unit_conversions")
    items_df = read_table("items")

    for item in items:
        item_id = item["item_id"]
        before_disp = item["current_display_qty"]
        after_disp = round(float(new_qty_map.get(item_id, before_disp)), 4)
        if abs(after_disp - before_disp) < 0.001:
            continue  # 無變化，跳過

        # 換算回 base_qty
        display_unit = item["display_unit"]
        base_unit = item["base_unit"]
        before_base = item["current_base_qty"]

        try:
            if display_unit == base_unit or not display_unit:
                after_base = after_disp
            else:
                after_base, _ = convert_to_base(
                    item_id=item_id,
                    qty=after_disp,
                    from_unit=display_unit,
                    items_df=items_df,
                    conversions_df=conversions_df,
                    as_of_date=adj_date,
                )
        except Exception:
            after_base = after_disp

        changed_items.append({
            "item_id": item_id,
            "item_name": item["item_name"],
            "vendor_id": item["vendor_id"],
            "before_display_qty": before_disp,
            "after_display_qty": after_disp,
            "display_unit": display_unit,
            "before_base_qty": before_base,
            "after_base_qty": round(after_base, 4),
            "base_unit": base_unit,
        })

    # ── 確認提交 ──────────────────────────────────────────────
    st.markdown("---")
    if changed_items:
        st.info(f"共 {len(changed_items)} 個品項有變動")
    else:
        st.caption("目前無品項變動。")

    if st.button("✅ 確認調整", disabled=(not changed_items), use_container_width=True):
        _show_confirm_dialog(store_id, adj_date, changed_items)


@st.dialog("確認庫存調整")
def _show_confirm_dialog(store_id: str, adj_date: date, changed_items: list[dict]):
    """確認彈窗：顯示調整摘要並寫入。"""
    st.markdown(f"**調整日期**：{adj_date.isoformat()}")
    st.markdown(f"**調整品項**：{len(changed_items)} 個")
    st.markdown("---")

    for item in changed_items:
        delta = round(item["after_display_qty"] - item["before_display_qty"], 4)
        delta_str = f"+{delta:g}" if delta > 0 else f"{delta:g}"
        uname = unit_label(item["display_unit"])
        st.write(
            f"• {item['item_name']}：{item['before_display_qty']:g} → {item['after_display_qty']:g} "
            f"{uname}（{delta_str}）"
        )

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 確認送出", use_container_width=True, key="adj_confirm_ok"):
            actor = str(st.session_state.get("login_user", "unknown")).strip()
            success, msg = save_adjustment(store_id, adj_date, actor, changed_items)
            if success:
                # 清除快取，讓下次重新載入
                for key in list(st.session_state.keys()):
                    if key.startswith("_stock_adj_"):
                        del st.session_state[key]
                bust_cache(["stocktakes", "stocktake_lines", "stock_adjustments"])
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    with col2:
        if st.button("✖ 取消", use_container_width=True, key="adj_confirm_cancel"):
            st.rerun()
