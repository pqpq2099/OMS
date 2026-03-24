# ============================================================
# ORIVIA OMS
# File: pages/page_order_entry.py
# Legacy compatibility source for order-related pages.
# New order entry/result pages should avoid adding new dependencies here.
# Legacy order entry page module
# Existing logic is preserved for compatibility
# ============================================================

from __future__ import annotations

from datetime import date
import requests
import streamlit as st
import pandas as pd

from oms_core import (
    _build_latest_item_metrics_df,
    _get_active_df,
    _item_display_name,
    _label_vendor,
    _norm,
    _safe_float,
    _sort_items_for_operation,
    _status_hint,
    get_table_versions,
    read_table,
)
from utils.utils_units import convert_unit


_ORDER_PAGE_TABLES = (
    "stores",
    "vendors",
    "items",
    "prices",
    "unit_conversions",
    "stocktakes",
    "stocktake_lines",
    "purchase_orders",
    "purchase_order_lines",
)


def _load_order_page_tables() -> dict[str, pd.DataFrame]:
    """集中載入叫貨頁常用資料，減少 rerun 時重複 read_table。"""
    versions = get_table_versions(_ORDER_PAGE_TABLES)
    cache = st.session_state.get("_order_page_tables_cache")
    if isinstance(cache, dict) and cache.get("versions") == versions:
        data = cache.get("data", {})
        if data:
            return {k: v.copy() for k, v in data.items()}

    data = {name: read_table(name) for name in _ORDER_PAGE_TABLES}
    st.session_state["_order_page_tables_cache"] = {
        "versions": versions,
        "data": {k: v.copy() for k, v in data.items()},
    }
    return {k: v.copy() for k, v in data.items()}


def _clear_order_page_tables_cache():
    st.session_state.pop("_order_page_tables_cache", None)


def send_line_message(line_message: str) -> bool:
    """
    把文字訊息推送到 LINE 群組。

    支援兩種 secrets 寫法：

    方案 A：扁平寫法
    LINE_CHANNEL_ACCESS_TOKEN = "xxx"
    LINE_GROUP_ID = "xxx"

    方案 B：巢狀寫法（建議）
    [line_bot]
    channel_access_token = "xxx"

    [line_groups]
    STORE_001 = "群組ID"
    STORE_002 = "群組ID"

    規則：
    1. 先依目前分店的 store_id 去 line_groups 找群組
    2. 若找不到，再 fallback 到 LINE_GROUP_ID
    """

    try:
        # ------------------------------------------------------------
        # 取得目前分店代碼
        # ------------------------------------------------------------
        store_id = str(st.session_state.get("store_id", "")).strip()

        # ------------------------------------------------------------
        # 讀取 token：先扁平，再巢狀
        # ------------------------------------------------------------
        channel_access_token = str(
            st.secrets.get("LINE_CHANNEL_ACCESS_TOKEN", "")
        ).strip()

        if not channel_access_token:
            try:
                line_bot_cfg = st.secrets.get("line_bot", {})
                channel_access_token = str(
                    line_bot_cfg.get("channel_access_token", "")
                ).strip()
            except Exception:
                channel_access_token = ""

        # ------------------------------------------------------------
        # 讀取 group_id：
        # 1. 先依 store_id 從 line_groups 抓
        # 2. 抓不到再 fallback 到扁平 LINE_GROUP_ID
        # ------------------------------------------------------------
        group_id = ""

        try:
            line_groups_cfg = st.secrets.get("line_groups", {})
            if store_id:
                group_id = str(line_groups_cfg.get(store_id, "")).strip()
        except Exception:
            group_id = ""

        if not group_id:
            group_id = str(
                st.secrets.get("LINE_GROUP_ID", "")
            ).strip()

        # ------------------------------------------------------------
        # 驗證必要設定
        # ------------------------------------------------------------
        if not channel_access_token:
            st.error(
                "缺少 LINE token，請檢查 Streamlit secrets："
                "LINE_CHANNEL_ACCESS_TOKEN 或 [line_bot].channel_access_token"
            )
            return False

        if not group_id:
            if store_id:
                st.error(
                    f"找不到分店 {store_id} 對應的 LINE 群組，"
                    "請檢查 [line_groups] 或 LINE_GROUP_ID 設定。"
                )
            else:
                st.error("缺少 LINE 群組設定，請檢查 [line_groups] 或 LINE_GROUP_ID。")
            return False

        # ------------------------------------------------------------
        # 呼叫 LINE Push API
        # ------------------------------------------------------------
        url = "https://api.line.me/v2/bot/message/push"

        headers = {
            "Authorization": f"Bearer {channel_access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "to": group_id,
            "messages": [
                {
                    "type": "text",
                    "text": line_message,
                }
            ],
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=15,
        )

        if response.status_code == 200:
            return True

        st.error(f"LINE API 錯誤：{response.status_code} / {response.text}")
        return False

    except Exception as e:
        st.error(f"發送 LINE 時發生錯誤：{e}")
        return False
# ============================================================
# [B1] 盤點引擎輔助函式
# 這一區放：抓上一筆庫存、建立本次新庫存
# 規則：
# 1. 有輸入 → 用新值覆蓋
# 2. 未輸入 → 沿用上一筆


def _convert_metric_base_to_stock_display_qty(
    *,
    item_id: str,
    qty: float,
    stock_unit: str,
    base_unit: str,
    conversions_df: pd.DataFrame,
    as_of_date: date,
) -> float:
    qty = _safe_float(qty, 0)
    item_id = _norm(item_id)
    stock_unit = _norm(stock_unit)
    base_unit = _norm(base_unit)

    if not item_id or not stock_unit:
        return round(qty, 1)

    if qty == 0 or stock_unit == base_unit or not base_unit:
        return round(qty, 1)

    try:
        converted = convert_unit(
            item_id=item_id,
            qty=qty,
            from_unit=base_unit,
            to_unit=stock_unit,
            conversions_df=conversions_df,
            as_of_date=as_of_date,
        )
        return round(converted, 1)
    except Exception:
        return round(qty, 1)


def _convert_metric_base_to_order_display_qty(
    *,
    item_id: str,
    qty: float,
    order_unit: str,
    base_unit: str,
    conversions_df: pd.DataFrame,
    as_of_date: date,
) -> float:
    qty = _safe_float(qty, 0)
    item_id = _norm(item_id)
    order_unit = _norm(order_unit)
    base_unit = _norm(base_unit)

    if not item_id or not order_unit:
        return round(qty, 1)

    if qty == 0 or order_unit == base_unit or not base_unit:
        return round(qty, 1)

    try:
        converted = convert_unit(
            item_id=item_id,
            qty=qty,
            from_unit=base_unit,
            to_unit=order_unit,
            conversions_df=conversions_df,
            as_of_date=as_of_date,
        )
        return round(converted, 1)
    except Exception:
        return round(qty, 1)


def _fmt_qty_with_unit(qty: float, unit: str) -> str:
    qty = _safe_float(qty, 0)
    unit = _norm(unit)
    if unit:
        return f"{qty:g}{unit}"
    return f"{qty:g}"



# ============================================================
# [B2] 到貨日 / 既有訂單修改輔助函式
# ============================================================
WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"]
WEEKDAY_OPTIONS = [f"星期{x}" for x in WEEKDAY_LABELS]



def page_order_entry():
    from operations.pages.page_order import page_order
    return page_order()


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

    page_tables = _load_order_page_tables()
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
            ok = send_line_message(line_message)
            if ok:
                st.success("✅ 已成功發送到 LINE")
            else:
                st.error("❌ LINE 發送失敗，請檢查 line_bot / line_groups 設定")

    with c2:
        if st.button("⬅️ 返回功能選單", use_container_width=True, key="back_from_order_message_detail"):
            st.session_state.step = "select_vendor"
            st.rerun()



# ============================================================
# [E4] Daily Stock Order Record / 當日庫存叫貨紀錄
# 說明：
# 1. 顯示指定日期、指定廠商的最近一筆庫存/叫貨紀錄
# 2. 畫面風格比照叫貨頁
# 3. 完全唯讀，不可編輯


def page_daily_stock_order_record():
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

    st.title("📋 當日庫存叫貨紀錄")

    store_id = _norm(st.session_state.get("store_id", ""))
    store_name = st.session_state.get("store_name", "")

    if not store_id:
        st.warning("請先選擇分店。")
        if st.button("⬅️ 返回分店列表", use_container_width=True):
            st.session_state.step = "select_store"
            st.rerun()
        return

    selected_date = st.date_input(
        "📅 日期",
        value=st.session_state.get("record_date", date.today()),
        key="daily_record_date",
    )

    page_tables = _load_order_page_tables()
    vendors_df = _get_active_df(page_tables["vendors"])
    items_df = _get_active_df(page_tables["items"])
    stocktakes_df = page_tables["stocktakes"]
    stocktake_lines_df = page_tables["stocktake_lines"]
    po_df = page_tables["purchase_orders"]
    pol_df = page_tables["purchase_order_lines"]

    if vendors_df.empty or items_df.empty:
        st.warning("⚠️ 廠商或品項資料讀取失敗")
        return

    # 只顯示目前有品項綁定的啟用廠商
    item_vendor_ids = set(items_df.get("default_vendor_id", pd.Series(dtype=str)).astype(str).str.strip())
    vendors = vendors_df[
        vendors_df["vendor_id"].astype(str).str.strip().isin(item_vendor_ids)
    ].copy()

    if vendors.empty:
        st.info("目前沒有可用廠商")
        return

    vendors["vendor_label"] = vendors.apply(_label_vendor, axis=1)
    vendors = vendors.sort_values(by=["vendor_label"], ascending=True).reset_index(drop=True)

    default_vendor_id = _norm(st.session_state.get("vendor_id", ""))
    vendor_id_to_label = {
        _norm(r.get("vendor_id", "")): r.get("vendor_label", "")
        for _, r in vendors.iterrows()
    }
    vendor_label_to_id = {
        r.get("vendor_label", ""): _norm(r.get("vendor_id", ""))
        for _, r in vendors.iterrows()
    }

    vendor_labels = vendors["vendor_label"].tolist()
    default_index = 0
    if default_vendor_id and default_vendor_id in vendor_id_to_label:
        default_label = vendor_id_to_label[default_vendor_id]
        if default_label in vendor_labels:
            default_index = vendor_labels.index(default_label)

    selected_vendor_label = st.selectbox(
        "🏢 選擇廠商",
        options=vendor_labels,
        index=default_index,
        key="daily_record_vendor",
    )
    vendor_id = vendor_label_to_id.get(selected_vendor_label, "")

    vendor_items = items_df[
        items_df["default_vendor_id"].astype(str).str.strip() == vendor_id
    ].copy()

    if vendor_items.empty:
        st.info("此廠商目前沒有對應品項")
        return

    vendor_items = _sort_items_for_operation(vendor_items).reset_index(drop=True)

    # -----------------------------
    # 取得當日最新叫貨單
    # -----------------------------
    po_work = po_df.copy()
    if not po_work.empty:
        po_work["store_id"] = po_work["store_id"].astype(str).str.strip()
        po_work["vendor_id"] = po_work["vendor_id"].astype(str).str.strip()
        po_work["order_date_dt"] = pd.to_datetime(po_work.get("order_date"), errors="coerce")
        po_work["created_at_dt"] = pd.to_datetime(po_work.get("created_at"), errors="coerce")

        po_work = po_work[
            (po_work["store_id"] == store_id) &
            (po_work["vendor_id"] == vendor_id) &
            (po_work["order_date_dt"].dt.date == selected_date)
        ].copy()
    latest_po_id = ""
    if not po_work.empty:
        sort_cols = [c for c in ["created_at_dt", "order_date_dt"] if c in po_work.columns]
        if sort_cols:
            po_work = po_work.sort_values(sort_cols, ascending=True)
        latest_po = po_work.tail(1).iloc[0]
        latest_po_id = _norm(latest_po.get("po_id", ""))

    order_map = {}
    if latest_po_id and not pol_df.empty:
        pol_work = pol_df.copy()
        pol_work["po_id"] = pol_work["po_id"].astype(str).str.strip()
        pol_work = pol_work[pol_work["po_id"] == latest_po_id].copy()

        for _, r in pol_work.iterrows():
            item_id = _norm(r.get("item_id", ""))
            if not item_id:
                continue
            order_map[item_id] = {
                "order_qty": _safe_float(r.get("order_qty", 0)),
                "order_unit": _norm(r.get("order_unit", "")),
            }

    # -----------------------------
    # 取得當日最新盤點
    # 說明：
    # 1. 先用 stocktakes 主表抓同分店、同日期的盤點批次
    # 2. vendor_id 若有寫入就優先精準比對
    # 3. 若主表 vendor_id 為空，改由 stocktake_lines 的 vendor_id 補抓
    # 4. 最後逐品項取最新一筆，避免整批找得到但明細抓不到
    # -----------------------------
    stocktake_map = {}
    if not stocktakes_df.empty and not stocktake_lines_df.empty:
        st_work = stocktakes_df.copy()
        stl_work = stocktake_lines_df.copy()

        if "stocktake_id" not in st_work.columns or "stocktake_id" not in stl_work.columns:
            st_work = pd.DataFrame()
        else:
            st_work["stocktake_id"] = st_work["stocktake_id"].astype(str).str.strip()
            st_work["store_id"] = st_work.get("store_id", "").astype(str).str.strip()
            st_work["vendor_id"] = st_work.get("vendor_id", "").astype(str).str.strip()
            st_work["stocktake_date_dt"] = pd.to_datetime(st_work.get("stocktake_date"), errors="coerce")
            st_work["created_at_dt"] = pd.to_datetime(st_work.get("created_at"), errors="coerce")

            stl_work["stocktake_id"] = stl_work["stocktake_id"].astype(str).str.strip()
            stl_work["store_id"] = stl_work.get("store_id", "").astype(str).str.strip()
            stl_work["vendor_id"] = stl_work.get("vendor_id", "").astype(str).str.strip()
            stl_work["item_id"] = stl_work.get("item_id", "").astype(str).str.strip()
            stl_work["created_at_dt"] = pd.to_datetime(stl_work.get("created_at"), errors="coerce")

            # 先抓同分店、同日期主表
            st_work = st_work[
                (st_work["store_id"] == store_id) &
                (st_work["stocktake_date_dt"].dt.date == selected_date)
            ].copy()

            if not st_work.empty:
                exact_st = st_work[st_work["vendor_id"] == vendor_id].copy()
                candidate_stocktake_ids = set()

                # 優先使用主表 vendor_id 精準命中的批次
                if not exact_st.empty:
                    candidate_stocktake_ids = set(exact_st["stocktake_id"].tolist())
                else:
                    # 若主表 vendor_id 沒寫到，退回由明細 vendor_id 補抓
                    same_day_ids = set(st_work["stocktake_id"].tolist())
                    stl_same_day = stl_work[stl_work["stocktake_id"].isin(same_day_ids)].copy()
                    if not stl_same_day.empty:
                        stl_same_day = stl_same_day[
                            (stl_same_day["store_id"] == store_id) &
                            (stl_same_day["vendor_id"] == vendor_id)
                        ].copy()
                        candidate_stocktake_ids = set(stl_same_day["stocktake_id"].tolist())

                if candidate_stocktake_ids:
                    stl_pick = stl_work[stl_work["stocktake_id"].isin(candidate_stocktake_ids)].copy()
                    stl_pick = stl_pick[
                        (stl_pick["store_id"] == store_id) &
                        (stl_pick["vendor_id"] == vendor_id)
                    ].copy()

                    # 若明細 vendor_id 也沒有寫到，最後退回同批次全部明細
                    if stl_pick.empty:
                        stl_pick = stl_work[stl_work["stocktake_id"].isin(candidate_stocktake_ids)].copy()

                    if not stl_pick.empty:
                        meta_cols = [c for c in ["stocktake_id", "stocktake_date_dt", "created_at_dt"] if c in st_work.columns]
                        stl_pick = stl_pick.merge(
                            st_work[meta_cols].drop_duplicates(subset=["stocktake_id"]),
                            on="stocktake_id",
                            how="left",
                            suffixes=("", "_main"),
                        )

                        if "created_at_dt_main" in stl_pick.columns:
                            stl_pick["sort_created_at"] = stl_pick["created_at_dt_main"]
                        else:
                            stl_pick["sort_created_at"] = stl_pick["created_at_dt"]

                        if "stocktake_date_dt" not in stl_pick.columns:
                            stl_pick["stocktake_date_dt"] = pd.NaT

                        stl_pick = stl_pick.sort_values(
                            by=["sort_created_at", "stocktake_date_dt"],
                            ascending=True,
                            na_position="last",
                        )

                        # 同一品項若當天重複送出，取最後一筆
                        latest_by_item = stl_pick.drop_duplicates(subset=["item_id"], keep="last")

                        for _, r in latest_by_item.iterrows():
                            item_id = _norm(r.get("item_id", ""))
                            if not item_id:
                                continue

                            stock_qty = r.get("stock_qty", r.get("qty", 0))
                            stock_unit = r.get("stock_unit", r.get("unit_id", ""))

                            stocktake_map[item_id] = {
                                "stock_qty": _safe_float(stock_qty),
                                "stock_unit": _norm(stock_unit),
                            }

    if not order_map and not stocktake_map:
        st.info("這一天目前沒有找到庫存 / 叫貨紀錄。")
        if st.button("⬅️ 返回廠商選單", use_container_width=True):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    latest_metrics_df = _build_latest_item_metrics_df(
        store_id=store_id,
        as_of_date=selected_date,
    )

    latest_metrics_map = {}
    if not latest_metrics_df.empty:
        latest_metrics_df = latest_metrics_df.copy()
        if "vendor_id" in latest_metrics_df.columns:
            latest_metrics_df["vendor_id"] = latest_metrics_df["vendor_id"].astype(str).str.strip()
            latest_metrics_df = latest_metrics_df[
                latest_metrics_df["vendor_id"] == str(vendor_id).strip()
            ].copy()
        for _, m in latest_metrics_df.iterrows():
            latest_metrics_map[_norm(m.get("item_id", ""))] = m.to_dict()

    st.caption(f"{store_name}｜{selected_vendor_label}｜最近一筆紀錄")

    st.markdown("<div class='order-divider'></div>", unsafe_allow_html=True)

    h1, h2, h3 = st.columns([6, 1, 1])
    h1.write("**品項名稱（建議量=日均×1.5）**")
    h2.write("<div style='text-align:center;'><b>庫</b></div>", unsafe_allow_html=True)
    h3.write("<div style='text-align:center;'><b>進</b></div>", unsafe_allow_html=True)

    for _, row in vendor_items.iterrows():
        item_id = _norm(row.get("item_id", ""))
        item_name = _item_display_name(row)

        base_unit = _norm(row.get("base_unit", ""))
        stock_unit_default = _norm(row.get("default_stock_unit", "")) or base_unit
        order_unit_default = _norm(row.get("default_order_unit", "")) or base_unit

        metric = latest_metrics_map.get(item_id, {})
        total_stock_ref = _safe_float(metric.get("庫存合計", 0))
        daily_avg = _safe_float(metric.get("日平均", 0))
        suggest_qty = round(daily_avg * 1.5, 1)
        status_hint = _norm(_status_hint(total_stock_ref, daily_avg, suggest_qty))
        total_stock_display = _convert_metric_base_to_stock_display_qty(
            item_id=item_id,
            qty=total_stock_ref,
            stock_unit=stock_unit_default,
            base_unit=base_unit,
            conversions_df=page_tables["unit_conversions"] if "unit_conversions" in page_tables else pd.DataFrame(),
            as_of_date=selected_date,
        )
        suggest_display = _convert_metric_base_to_stock_display_qty(
            item_id=item_id,
            qty=suggest_qty,
            stock_unit=stock_unit_default,
            base_unit=base_unit,
            conversions_df=page_tables["unit_conversions"] if "unit_conversions" in page_tables else pd.DataFrame(),
            as_of_date=selected_date,
        )

        stock_info = stocktake_map.get(item_id, {})
        order_info = order_map.get(item_id, {})

        stock_qty = _safe_float(stock_info.get("stock_qty", 0))
        stock_unit = _norm(stock_info.get("stock_unit", "")) or stock_unit_default

        order_qty = _safe_float(order_info.get("order_qty", 0))
        order_unit = _norm(order_info.get("order_unit", "")) or order_unit_default

        c1, c2, c3 = st.columns([6, 1, 1])

        with c1:
            st.write(f"<b>{item_name}</b>", unsafe_allow_html=True)
            tail = f"　{status_hint}" if status_hint else ""
            st.markdown(
                f"<div class='order-meta'>總庫存：{_fmt_qty_with_unit(total_stock_display, stock_unit_default)}　建議量：{_fmt_qty_with_unit(suggest_display, stock_unit_default)}{tail}</div>",
                unsafe_allow_html=True,
            )

        with c2:
            st.number_input(
                "庫",
                min_value=0.0,
                step=0.1,
                format="%g",
                value=float(stock_qty),
                key=f"daily_record_stock_{item_id}",
                label_visibility="collapsed",
                disabled=True,
            )
            st.markdown(
                f"<div class='order-unit-label'>{stock_unit}</div>",
                unsafe_allow_html=True,
            )

        with c3:
            st.number_input(
                "進",
                min_value=0.0,
                step=0.1,
                format="%g",
                value=float(order_qty),
                key=f"daily_record_order_{item_id}",
                label_visibility="collapsed",
                disabled=True,
            )
            st.selectbox(
                "進貨單位",
                options=[order_unit or "-"],
                index=0,
                key=f"daily_record_unit_{item_id}",
                label_visibility="collapsed",
                disabled=True,
            )

    st.markdown("<div class='order-divider'></div>", unsafe_allow_html=True)

    if st.button("⬅️ 返回廠商選單", use_container_width=True):
        st.session_state.step = "select_vendor"
        st.rerun()







