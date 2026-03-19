# ============================================================
# ORIVIA OMS
# 檔案：pages/page_order_entry.py
# 說明：叫貨與庫存作業頁
# 功能：選擇分店、選擇廠商、進行庫存與叫貨輸入、產出 LINE 明細。
# 注意：這是營運核心頁，修改前要先確認現場流程。
# ============================================================

"""
頁面模組：叫貨流程與分店/廠商選擇。
這個檔案負責：
1. 選擇分店
2. 選擇廠商
3. 進入庫存/叫貨同頁
4. 產出 LINE 訊息明細

如果之後要改現場叫貨流程，優先看這個檔案。
"""

from __future__ import annotations

# ============================================================
# [A1] 基本匯入
# 這一區放：日期、Streamlit、核心函式
# ============================================================
from datetime import date, timedelta
import requests
import streamlit as st
import pandas as pd

from oms_core import (
    _build_latest_item_metrics_df,
    _build_stock_detail_df,
    _clean_option_list,
    _get_active_df,
    _get_last_po_summary,
    _get_latest_price_for_item,
    get_base_unit_cost,
    _get_latest_stock_qty_in_display_unit,
    _item_display_name,
    _label_store,
    _label_vendor,
    _norm,
    _now_ts,
    _parse_date,
    _safe_float,
    _sort_items_for_operation,
    _status_hint,
    allocate_ids,
    append_rows_by_header,
    bust_cache,
    get_header,
    get_spreadsheet,
    get_table_versions,
    read_table,
)
from utils.utils_units import convert_to_base


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

_SELECTOR_TABLES = ("stores", "vendors", "items")


def _load_selector_tables() -> dict[str, pd.DataFrame]:
    """分店/廠商選擇頁集中快取，降低切頁 rerun 時的讀取量。"""
    versions = get_table_versions(_SELECTOR_TABLES)
    cache = st.session_state.get("_selector_tables_cache")
    if isinstance(cache, dict) and cache.get("versions") == versions:
        data = cache.get("data", {})
        if data:
            return {k: v.copy() for k, v in data.items()}

    data = {name: read_table(name) for name in _SELECTOR_TABLES}
    st.session_state["_selector_tables_cache"] = {
        "versions": versions,
        "data": {k: v.copy() for k, v in data.items()},
    }
    return {k: v.copy() for k, v in data.items()}


def _clear_selector_tables_cache():
    st.session_state.pop("_selector_tables_cache", None)


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
# [B2] 到貨日 / 既有訂單修改輔助函式
# ============================================================
WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"]
WEEKDAY_OPTIONS = [f"星期{x}" for x in WEEKDAY_LABELS]


def _weekday_option_from_date(target_date: date | None, fallback: date | None = None) -> str:
    ref = target_date or fallback or date.today()
    return WEEKDAY_OPTIONS[ref.weekday()]


def _delivery_date_from_weekday(record_date: date, weekday_option: str) -> date:
    """把下拉選到的星期幾，換算成最近一次「大於等於作業日」的到貨日。"""
    text = str(weekday_option or "").strip().replace("禮拜", "星期")
    if text not in WEEKDAY_OPTIONS:
        return record_date

    target_weekday = WEEKDAY_OPTIONS.index(text)
    current_weekday = record_date.weekday()
    delta = target_weekday - current_weekday
    if delta < 0:
        delta += 7
    return record_date + timedelta(days=delta)


def _sheet_col_to_letter(n: int) -> str:
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result




def _normalize_compare_value(value):
    """把資料整理成適合比較的格式，避免型態差異造成誤判。"""
    if value is None:
        return ""

    text = str(value).strip()
    if text == "":
        return ""

    try:
        num = float(text)
        if num.is_integer():
            return str(int(num))
        return str(num)
    except Exception:
        return text


def _rows_equal_for_compare(old_map: dict, new_map: dict, header: list[str], ignore_fields: set[str] | None = None) -> bool:
    """比較兩列資料是否真的有業務內容差異。"""
    ignore_fields = ignore_fields or set()
    for col in header:
        if col in ignore_fields:
            continue
        old_v = _normalize_compare_value(old_map.get(col, ""))
        new_v = _normalize_compare_value(new_map.get(col, ""))
        if old_v != new_v:
            return False
    return True

def _update_row_by_id(sheet_name: str, id_field: str, entity_id: str, updates: dict):
    """
    更新主表單筆資料。
    只有當業務內容真的有變更時，才會寫回 Google Sheets。
    回傳值：
    - True  = 有實際更新
    - False = 資料內容相同，略過寫入
    """
    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet(sheet_name)
    header = [_norm(x) for x in ws.row_values(1)]
    if not header:
        raise ValueError(f"{sheet_name} 缺少表頭")

    if id_field not in header:
        raise ValueError(f"{sheet_name} 缺少 {id_field}")

    values = ws.get_all_values()
    if not values:
        raise ValueError(f"{sheet_name} 為空")

    id_idx = header.index(id_field)
    target_row_num = None
    for row_num, row in enumerate(values[1:], start=2):
        cell = row[id_idx] if id_idx < len(row) else ""
        if _norm(cell) == _norm(entity_id):
            target_row_num = row_num
            break

    if target_row_num is None:
        raise ValueError(f"{sheet_name} 找不到 {entity_id}")

    row_values = ws.row_values(target_row_num)
    if len(row_values) < len(header):
        row_values = row_values + [""] * (len(header) - len(row_values))
    else:
        row_values = row_values[:len(header)]

    current = {col: row_values[idx] for idx, col in enumerate(header)}
    candidate = dict(current)
    for key, value in updates.items():
        if key in candidate:
            candidate[key] = "" if value is None else value

    compare_ignore_fields = {"updated_at", "updated_by", "created_at", "created_by"}
    if _rows_equal_for_compare(current, candidate, header, compare_ignore_fields):
        return False

    new_row = [candidate.get(col, "") for col in header]
    end_col = _sheet_col_to_letter(len(header))
    ws.update(
        f"A{target_row_num}:{end_col}{target_row_num}",
        [new_row],
        value_input_option="USER_ENTERED",
    )
    return True

def _write_audit_log(action: str, table_name: str, entity_id: str, note: str, before_json: str = "{}", after_json: str = "{}"):
    try:
        header = get_header("audit_logs")
    except Exception:
        return

    if not header:
        return

    now = _now_ts()
    login_user_id = _norm(st.session_state.get("login_user_id", "")) or "SYSTEM"
    audit_id = f"AUDIT_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S%f')}"
    row = {c: "" for c in header}
    defaults = {
        "audit_id": audit_id,
        "ts": now,
        "user_id": login_user_id,
        "action": action,
        "table_name": table_name,
        "entity_id": entity_id,
        "before_json": before_json,
        "after_json": after_json,
        "note": note,
    }
    for k, v in defaults.items():
        if k in row:
            row[k] = v
    append_rows_by_header("audit_logs", header, [row])


def _find_existing_operation_ids(store_id: str, vendor_id: str, record_date: date) -> dict:
    result = {
        "stocktake_id": "",
        "po_id": "",
        "delivery_date": None,
    }

    target_date = str(record_date)

    stocktakes_df = read_table("stocktakes")
    if not stocktakes_df.empty and {"store_id", "vendor_id", "stocktake_date", "stocktake_id"}.issubset(stocktakes_df.columns):
        work = stocktakes_df.copy()
        work["stocktake_date_str"] = work["stocktake_date"].astype(str).str[:10]
        work = work[
            (work["store_id"].astype(str).str.strip() == str(store_id).strip())
            & (work["vendor_id"].astype(str).str.strip() == str(vendor_id).strip())
            & (work["stocktake_date_str"] == target_date)
        ].copy()
        if not work.empty:
            sort_cols = [c for c in ["updated_at", "created_at", "stocktake_id"] if c in work.columns]
            if sort_cols:
                work = work.sort_values(sort_cols, ascending=True)
            result["stocktake_id"] = _norm(work.iloc[-1].get("stocktake_id", ""))

    po_df = read_table("purchase_orders")
    if not po_df.empty and {"store_id", "vendor_id", "order_date", "po_id"}.issubset(po_df.columns):
        work = po_df.copy()
        work["order_date_str"] = work["order_date"].astype(str).str[:10]
        work = work[
            (work["store_id"].astype(str).str.strip() == str(store_id).strip())
            & (work["vendor_id"].astype(str).str.strip() == str(vendor_id).strip())
            & (work["order_date_str"] == target_date)
        ].copy()
        if not work.empty:
            sort_cols = [c for c in ["updated_at", "created_at", "po_id"] if c in work.columns]
            if sort_cols:
                work = work.sort_values(sort_cols, ascending=True)
            hit = work.iloc[-1]
            result["po_id"] = _norm(hit.get("po_id", ""))
            result["delivery_date"] = _parse_date(hit.get("delivery_date")) or _parse_date(hit.get("expected_date"))

    return result


def _get_existing_stock_map(stocktake_id: str) -> dict[str, float]:
    if not stocktake_id:
        return {}

    stock_lines_df = read_table("stocktake_lines")
    if stock_lines_df.empty or "stocktake_id" not in stock_lines_df.columns:
        return {}

    work = stock_lines_df[
        stock_lines_df["stocktake_id"].astype(str).str.strip() == str(stocktake_id).strip()
    ].copy()

    result = {}
    for _, row in work.iterrows():
        item_id = _norm(row.get("item_id", ""))
        if not item_id:
            continue
        result[item_id] = _safe_float(row.get("stock_qty", row.get("qty", 0)))
    return result


def _get_existing_order_maps(po_id: str) -> tuple[dict[str, float], dict[str, str]]:
    if not po_id:
        return {}, {}

    pol_df = read_table("purchase_order_lines")
    if pol_df.empty or "po_id" not in pol_df.columns:
        return {}, {}

    work = pol_df[
        pol_df["po_id"].astype(str).str.strip() == str(po_id).strip()
    ].copy()

    qty_map = {}
    unit_map = {}

    for _, row in work.iterrows():
        item_id = _norm(row.get("item_id", ""))
        if not item_id:
            continue
        qty_map[item_id] = _safe_float(row.get("order_qty", row.get("qty", 0)))
        unit_map[item_id] = _norm(row.get("order_unit", row.get("unit_id", "")))
    return qty_map, unit_map


def _upsert_detail_rows_by_parent(
    sheet_name: str,
    parent_field: str,
    parent_id: str,
    line_id_field: str,
    item_rows: list[dict],
    allocate_key: str,
):
    """
    同一張主單下，依 item_id 做 upsert：
    - 已存在：只有內容真的變更才覆寫該列
    - 不存在：新增

    回傳值：
    - True  = 有新增或更新
    - False = 全部內容相同，略過寫入
    """
    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet(sheet_name)
    header = [_norm(x) for x in ws.row_values(1)]
    values = ws.get_all_values()
    if not values:
        raise ValueError(f"{sheet_name} 為空")

    row_maps = []
    for row_num, row in enumerate(values[1:], start=2):
        row_values = list(row) + [""] * (len(header) - len(row))
        row_values = row_values[:len(header)]
        row_maps.append((row_num, {col: row_values[idx] for idx, col in enumerate(header)}))

    existing_by_item = {}
    for row_num, row_dict in row_maps:
        if _norm(row_dict.get(parent_field, "")) != _norm(parent_id):
            continue
        item_id = _norm(row_dict.get("item_id", ""))
        if item_id:
            existing_by_item[item_id] = (row_num, row_dict)

    add_rows = []
    new_id_list = []
    has_changed = False

    need_new = [r for r in item_rows if _norm(r.get("item_id", "")) not in existing_by_item]
    if need_new:
        allocated = allocate_ids({allocate_key: len(need_new)})
        new_id_list = allocated.get(allocate_key, [])

    new_idx = 0
    compare_ignore_fields = {"updated_at", "updated_by", "created_at", "created_by"}

    for item_row in item_rows:
        item_id = _norm(item_row.get("item_id", ""))
        if not item_id:
            continue

        if item_id in existing_by_item:
            row_num, row_dict = existing_by_item[item_id]
            current = dict(row_dict)
            candidate = dict(row_dict)
            for key, value in item_row.items():
                if key not in candidate:
                    continue
                if key in {"created_at", "created_by"}:
                    continue
                candidate[key] = "" if value is None else value

            if _rows_equal_for_compare(current, candidate, header, compare_ignore_fields):
                continue

            end_col = _sheet_col_to_letter(len(header))
            ws.update(
                f"A{row_num}:{end_col}{row_num}",
                [[candidate.get(col, "") for col in header]],
                value_input_option="USER_ENTERED",
            )
            has_changed = True
        else:
            row_dict = {c: "" for c in header}
            if line_id_field in row_dict and new_idx < len(new_id_list):
                row_dict[line_id_field] = new_id_list[new_idx]
                new_idx += 1
            for key, value in item_row.items():
                if key in row_dict:
                    row_dict[key] = "" if value is None else value
            add_rows.append(row_dict)

    if add_rows:
        append_rows_by_header(sheet_name, header, add_rows)
        has_changed = True

    return has_changed

# ============================================================
# [E1] Select Store / 選擇分店頁
# 你之後如果要改：
# 1. 分店按鈕顯示方式
# 2. 分店排序
# 3. 選到分店後要先清掉哪些 session_state
# 看這一段。
# ============================================================
def page_select_store():
    st.markdown(
        "<style>.block-container { padding-top: 4rem !important; }</style>",
        unsafe_allow_html=True,
    )
    st.title("🏠 選擇分店")

    selector_tables = _load_selector_tables()
    stores_df = _get_active_df(selector_tables["stores"])
    if stores_df.empty:
        st.warning("⚠️ 分店資料讀取失敗")
        return

    login_role_id = str(st.session_state.get("login_role_id", "")).strip().lower()
    login_store_scope = str(st.session_state.get("login_store_scope", "")).strip()

    stores_df = stores_df.copy()
    if login_role_id not in ["owner", "admin", "test_admin"]:
        if not login_store_scope or login_store_scope == "ALL":
            st.error("此帳號尚未綁定可用分店，請聯絡管理員設定。")
            return

        stores_df = stores_df[
            stores_df["store_id"].astype(str).str.strip() == login_store_scope
        ].copy()

        if stores_df.empty:
            st.error("此帳號沒有可操作的分店，請檢查 store_scope 設定。")
            return

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
# [E2] Select Vendor / 選擇廠商頁
# 你之後如果要改：
# 1. 廠商按鈕排列方式
# 2. 要不要顯示所有廠商 / 僅顯示有品項的廠商
# 3. 報表入口按鈕的位置
# 看這一段。
# ============================================================
def page_select_vendor():
    st.markdown(
        "<style>.block-container { padding-top: 4rem !important; }</style>",
        unsafe_allow_html=True,
    )
    st.title(f"🏢 {st.session_state.store_name}")

    selected_record_date = st.date_input(
        "🗓️ 作業日期",
        value=st.session_state.get("record_date", date.today()),
        key="select_vendor_record_date",
    )
    st.session_state.record_date = selected_record_date

    selector_tables = _load_selector_tables()
    vendors_df = _get_active_df(selector_tables["vendors"])
    items_df = _get_active_df(selector_tables["items"])

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
        st.session_state.step = "order_message_detail"
        st.rerun()

    if st.button("📈 期間進銷存分析", use_container_width=True):
        st.session_state.step = "analysis"
        st.rerun()

    if st.button("📜 查看歷史叫貨紀錄", use_container_width=True):
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

# ============================================================
# [E3] Order Entry / 庫存+叫貨同頁主畫面
# 這是你最常改的檔案核心。
# 你之後最可能調整的內容：
# 1. 品項顯示順序
# 2. 每列顯示哪些資訊（總庫存、建議量、單價、上次叫貨）
# 3. 手機版欄位寬度
# 4. 建議量顏色提示
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

    page_tables = _load_order_page_tables()
    items_df = _get_active_df(page_tables["items"])
    prices_df = page_tables["prices"]
    conversions_df = _get_active_df(page_tables["unit_conversions"])
    stocktakes_df = page_tables["stocktakes"]
    stocktake_lines_df = page_tables["stocktake_lines"]
    po_df = page_tables["purchase_orders"]
    pol_df = page_tables["purchase_order_lines"]

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

    existing_ids = _find_existing_operation_ids(
        store_id=st.session_state.store_id,
        vendor_id=st.session_state.vendor_id,
        record_date=st.session_state.record_date,
    )
    existing_stock_map = _get_existing_stock_map(existing_ids.get("stocktake_id", ""))
    existing_order_qty_map, existing_order_unit_map = _get_existing_order_maps(existing_ids.get("po_id", ""))
    existing_delivery_option = _weekday_option_from_date(
        existing_ids.get("delivery_date"),
        st.session_state.record_date,
    )

    is_edit_mode = bool(existing_ids.get("stocktake_id") or existing_ids.get("po_id"))
    if is_edit_mode:
        st.info("ℹ️ 這一天此廠商已有紀錄，畫面已自動帶入，按下儲存會直接覆寫更新。")
        edit_lines = [f"作業日期：{st.session_state.record_date}"]
        if existing_ids.get("stocktake_id"):
            edit_lines.append(f"庫存單號：{existing_ids.get('stocktake_id')}")
        if existing_ids.get("po_id"):
            edit_lines.append(f"叫貨單號：{existing_ids.get('po_id')}")
        if existing_ids.get("delivery_date"):
            edit_lines.append(f"原到貨日：{existing_ids.get('delivery_date')}")
        st.caption("｜".join(edit_lines))

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

        current_stock_qty = existing_stock_map.get(item_id)
        if current_stock_qty is None:
            current_stock_qty = _get_latest_stock_qty_in_display_unit(
                stocktakes_df=stocktakes_df,
                stocktake_lines_df=stocktake_lines_df,
                items_df=vendor_items,
                conversions_df=conversions_df,
                store_id=st.session_state.store_id,
                item_id=item_id,
                display_unit=stock_unit,
                as_of_date=st.session_state.record_date,
            )

        metric = latest_metrics_map.get(item_id, {})
        period_purchase = _safe_float(metric.get("期間進貨", 0))
        period_usage = _safe_float(metric.get("期間消耗", 0))
        daily_avg = _safe_float(metric.get("日平均", 0))
        total_stock_ref = _safe_float(metric.get("庫存合計", 0))
        suggest_qty = round(daily_avg * 1.5, 1)
        status_hint = _status_hint(total_stock_ref, daily_avg, suggest_qty)

        if period_purchase > 0 or period_usage > 0 or total_stock_ref > 0 or current_stock_qty > 0:
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
            "existing_order_qty": round(_safe_float(existing_order_qty_map.get(item_id, 0)), 1),
            "existing_order_unit": _norm(existing_order_unit_map.get(item_id, "")) or order_unit,
        }

    ref_df = None
    if ref_rows:
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
                    min_value=0.0,
                    step=0.1,
                    format="%g",
                    value=float(current_stock_qty),
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
                    value=float(meta["existing_order_qty"]),
                    key=f"order_{item_id}",
                    label_visibility="collapsed",
                )
                selected_order_unit = st.selectbox(
                    "進貨單位",
                    options=meta["orderable_unit_options"],
                    index=meta["orderable_unit_options"].index(meta["existing_order_unit"])
                    if meta["existing_order_unit"] in meta["orderable_unit_options"]
                    else (meta["orderable_unit_options"].index(order_unit) if order_unit in meta["orderable_unit_options"] else 0),
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

        st.markdown("<div class='order-divider'></div>", unsafe_allow_html=True)

        selected_delivery_weekday = st.selectbox(
            "到貨星期",
            options=WEEKDAY_OPTIONS,
            index=WEEKDAY_OPTIONS.index(existing_delivery_option) if existing_delivery_option in WEEKDAY_OPTIONS else 0,
            key="delivery_weekday_option",
        )
        delivery_date = _delivery_date_from_weekday(st.session_state.record_date, selected_delivery_weekday)
        st.caption(f"本次到貨日：{delivery_date.strftime('%Y-%m-%d')}（{WEEKDAY_LABELS[delivery_date.weekday()]}）")

        submitted = st.form_submit_button("💾 儲存並同步", use_container_width=True)

        if submitted:
            errors = []
    
            has_any_order = any(_safe_float(r["order_qty"]) > 0 for r in submit_rows)
            has_any_stock_gt_zero = any(_safe_float(r["stock_qty"]) > 0 for r in submit_rows)
    
            # 初始化防呆：不可全部 0 且完全沒叫貨
            if is_initial_stock and (not has_any_order) and (not has_any_stock_gt_zero):
                errors.append("初始化庫存不可全部為 0，且不可完全沒有叫貨。")
    
            # 有叫貨的品項，必須有有效價格
            prices_df_for_check = read_table("prices")
            for r in submit_rows:
                if _safe_float(r["order_qty"]) <= 0:
                    continue

                try:
                    order_base_qty_check, _ = convert_to_base(
                        item_id=r["item_id"],
                        qty=r["order_qty"],
                        from_unit=r["order_unit"],
                        items_df=vendor_items,
                        conversions_df=conversions_df,
                        as_of_date=st.session_state.record_date,
                    )
                    base_unit_cost_check = get_base_unit_cost(
                        item_id=r["item_id"],
                        target_date=st.session_state.record_date,
                        items_df=vendor_items,
                        prices_df=prices_df_for_check,
                        conversions_df=conversions_df,
                    )
                    check_amount = round(float(order_base_qty_check) * float(base_unit_cost_check or 0), 1)
                except Exception:
                    check_amount = 0

                if check_amount <= 0:
                    errors.append(f"{r['item_name']} 缺少有效價格設定，無法送出。")
    
            if errors:
                for msg in errors:
                    st.error(msg)
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
                    is_initial_stock=is_initial_stock,
                )
    
                action_text = "✅ 已修改完成" if is_edit_mode else "✅ 已儲存完成"
                tail_text = ('並建立/更新叫貨單：' + po_id) if po_id else '本次無叫貨品項'
                st.success(f"{action_text}；{tail_text}")
                st.session_state.step = "select_vendor"
                st.rerun()
    
            except Exception as e:
                st.error(f"❌ 儲存失敗：{e}")
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

# ============================================================
# [E4] 儲存叫貨/庫存資料
# 這一段是「按下送出後，真正寫入 stocktake / purchase_order」的核心。
# 若之後遇到：
# 1. 0 值是否寫入
# 2. delivery_date / order_date 計算
# 3. 明細寫入欄位錯誤
# 優先檢查這裡。
# ============================================================
def _save_order_entry(
    submit_rows,
    vendor_items,
    conversions_df,
    store_id,
    vendor_id,
    record_date,
    delivery_date,
    existing_stocktake_id: str = "",
    existing_po_id: str = "",
    is_initial_stock: bool = False,
):
    now = _now_ts()
    user_id = _norm(st.session_state.get("login_user_id", "")) or "SYSTEM"
    prices_df = read_table("prices")

    order_rows = [r for r in submit_rows if _safe_float(r["order_qty"]) > 0]
    stocktake_rows = []
    for r in submit_rows:
        item_id = _norm(r.get("item_id", ""))
        if not item_id:
            continue
        stocktake_rows.append(
            {
                "item_id": item_id,
                "item_name": r.get("item_name", ""),
                "stock_qty": _safe_float(r.get("stock_qty", 0)),
                "stock_unit": _norm(r.get("stock_unit", "")),
            }
        )

    po_id = _norm(existing_po_id)
    stocktake_id = _norm(existing_stocktake_id)

    stocktake_main_changed = False
    stocktake_line_changed = False
    po_main_changed = False
    po_line_changed = False

    # ============================================================
    # 1. stocktakes / stocktake_lines
    #    若同日同廠商已有資料，直接覆寫；否則新增。
    # ============================================================
    if stocktake_rows:
        stocktake_header = get_header("stocktakes")
        stl_header = get_header("stocktake_lines")

        if stocktake_id:
            stocktake_main_changed = _update_row_by_id(
                "stocktakes",
                "stocktake_id",
                stocktake_id,
                {
                    "store_id": store_id,
                    "vendor_id": vendor_id,
                    "stocktake_date": str(record_date),
                    "status": "done",
                    "note": "initial_stock" if is_initial_stock else f"vendor={vendor_id}",
                    "updated_at": now,
                    "updated_by": user_id,
                },
            )
        else:
            id_map = allocate_ids({"stocktakes": 1})
            stocktake_id = id_map["stocktakes"][0]
            stocktake_main_row = {c: "" for c in stocktake_header}
            defaults = {
                "stocktake_id": stocktake_id,
                "store_id": store_id,
                "vendor_id": vendor_id,
                "stocktake_date": str(record_date),
                "stocktake_type": "initial" if is_initial_stock else "regular",
                "status": "done",
                "note": "initial_stock" if is_initial_stock else f"vendor={vendor_id}",
                "created_at": now,
                "created_by": user_id,
            }
            for k, v in defaults.items():
                if k in stocktake_main_row:
                    stocktake_main_row[k] = v
            append_rows_by_header("stocktakes", stocktake_header, [stocktake_main_row])
            stocktake_main_changed = True

        stock_line_rows = []
        for r in stocktake_rows:
            try:
                stock_base_qty, stock_base_unit = convert_to_base(
                    item_id=r["item_id"],
                    qty=r["stock_qty"],
                    from_unit=r["stock_unit"],
                    items_df=vendor_items,
                    conversions_df=conversions_df,
                    as_of_date=record_date,
                )
            except Exception as e:
                raise ValueError(f"{r['item_name']} 庫存單位換算失敗：{e}")

            row_dict = {c: "" for c in stl_header}
            defaults_line = {
                "stocktake_id": stocktake_id,
                "store_id": store_id,
                "vendor_id": vendor_id,
                "item_id": r["item_id"],
                "item_name": r["item_name"],
                "qty": str(r["stock_qty"]),
                "stock_qty": str(r["stock_qty"]),
                "unit_id": r["stock_unit"],
                "stock_unit": r["stock_unit"],
                "stock_unit_id": r["stock_unit"],
                "base_qty": str(round(stock_base_qty, 3)),
                "base_unit": stock_base_unit,
                "updated_at": now,
                "updated_by": user_id,
                "created_at": now,
                "created_by": user_id,
            }
            for k, v in defaults_line.items():
                if k in row_dict:
                    row_dict[k] = v
            stock_line_rows.append(row_dict)

        stocktake_line_changed = _upsert_detail_rows_by_parent(
            sheet_name="stocktake_lines",
            parent_field="stocktake_id",
            parent_id=stocktake_id,
            line_id_field="stocktake_line_id",
            item_rows=stock_line_rows,
            allocate_key="stocktake_lines",
        )
        if stocktake_main_changed or stocktake_line_changed:
            _write_audit_log(
                action="update_stocktake" if existing_stocktake_id else "create_stocktake",
                table_name="stocktakes",
                entity_id=stocktake_id,
                note=f"store={store_id}, vendor={vendor_id}, date={record_date}",
            )

    # ============================================================
    # 2. purchase_orders / purchase_order_lines
    #    若同日同廠商已有資料，直接覆寫；若原本有單但這次全為 0，則視為清空叫貨。
    # ============================================================
    po_header = get_header("purchase_orders")
    pol_header = get_header("purchase_order_lines")

    if po_id:
        status_value = "draft" if order_rows else "cancelled"
        po_main_changed = _update_row_by_id(
            "purchase_orders",
            "po_id",
            po_id,
            {
                "store_id": store_id,
                "vendor_id": vendor_id,
                "po_date": str(record_date),
                "order_date": str(record_date),
                "expected_date": str(delivery_date),
                "delivery_date": str(delivery_date),
                "status": status_value,
                "updated_at": now,
                "updated_by": user_id,
            },
        )
    elif order_rows:
        id_map = allocate_ids({"purchase_orders": 1})
        po_id = id_map["purchase_orders"][0]
        po_row = {c: "" for c in po_header}
        defaults_po = {
            "po_id": po_id,
            "po_date": str(record_date),
            "store_id": store_id,
            "vendor_id": vendor_id,
            "order_date": str(record_date),
            "expected_date": str(delivery_date),
            "delivery_date": str(delivery_date),
            "status": "draft",
            "created_at": now,
            "created_by": user_id,
        }
        for k, v in defaults_po.items():
            if k in po_row:
                po_row[k] = v
        append_rows_by_header("purchase_orders", po_header, [po_row])
        po_main_changed = True

    if po_id:
        po_line_rows = []
        existing_qty_map, existing_unit_map = _get_existing_order_maps(po_id)
        target_item_ids = {_norm(r.get("item_id", "")) for r in submit_rows if _norm(r.get("item_id", ""))}

        existing_line_item_ids = {
            _norm(k) for k in list(existing_qty_map.keys()) + list(existing_unit_map.keys()) if _norm(k)
        }

        for r in submit_rows:
            item_id = _norm(r.get("item_id", ""))
            if item_id not in target_item_ids:
                continue

            order_qty = _safe_float(r.get("order_qty", 0))
            order_unit = _norm(r.get("order_unit", ""))
            item_name = r.get("item_name", "")

            # ------------------------------------------------------------
            # 寫入降載防呆：
            # 只有兩種情況才需要處理 purchase_order_lines：
            # 1. 本次真的有叫貨量 (>0)
            # 2. 這個品項原本就已存在叫貨明細，需要允許覆寫成 0
            #    （例如：修改訂單、把原本叫貨清掉）
            # 若原本沒有這筆明細，且本次也沒有叫貨，就直接跳過，
            # 避免為大量 0 值品項建立無意義明細，造成寫入次數暴增。
            # ------------------------------------------------------------
            if order_qty <= 0 and item_id not in existing_line_item_ids:
                continue

            if order_qty > 0:
                try:
                    order_base_qty, order_base_unit = convert_to_base(
                        item_id=r["item_id"],
                        qty=order_qty,
                        from_unit=order_unit,
                        items_df=vendor_items,
                        conversions_df=conversions_df,
                        as_of_date=record_date,
                    )
                except Exception as e:
                    raise ValueError(f"{item_name} 叫貨單位換算失敗：{e}")

                base_unit_cost = get_base_unit_cost(
                    item_id=r["item_id"],
                    target_date=record_date,
                    items_df=vendor_items,
                    prices_df=prices_df,
                    conversions_df=conversions_df,
                )
                if base_unit_cost is None or float(base_unit_cost) <= 0:
                    raise ValueError(f"{item_name} 缺少有效價格設定，無法計算叫貨金額。")

                line_amount = round(float(order_base_qty) * float(base_unit_cost), 1)
                order_unit_price = round(line_amount / float(order_qty), 4) if float(order_qty) > 0 else 0
            else:
                order_base_qty = 0
                order_base_unit = ""
                line_amount = 0
                order_unit_price = 0
                if not order_unit:
                    order_unit = _norm(existing_unit_map.get(r["item_id"], ""))

            row_dict = {c: "" for c in pol_header}
            defaults_pol = {
                "po_id": po_id,
                "store_id": store_id,
                "vendor_id": vendor_id,
                "item_id": r["item_id"],
                "item_name": item_name,
                "qty": str(order_qty),
                "order_qty": str(order_qty),
                "unit_id": order_unit,
                "order_unit": order_unit,
                "base_qty": str(round(order_base_qty, 3)),
                "base_unit": order_base_unit,
                "unit_price": str(order_unit_price),
                "amount": str(line_amount),
                "delivery_date": str(delivery_date),
                "updated_at": now,
                "updated_by": user_id,
                "created_at": now,
                "created_by": user_id,
            }
            for k, v in defaults_pol.items():
                if k in row_dict:
                    row_dict[k] = v
            po_line_rows.append(row_dict)

        po_line_changed = _upsert_detail_rows_by_parent(
            sheet_name="purchase_order_lines",
            parent_field="po_id",
            parent_id=po_id,
            line_id_field="po_line_id",
            item_rows=po_line_rows,
            allocate_key="purchase_order_lines",
        )
        if po_main_changed or po_line_changed:
            _write_audit_log(
                action="update_purchase_order" if existing_po_id else "create_purchase_order",
                table_name="purchase_orders",
                entity_id=po_id,
                note=f"store={store_id}, vendor={vendor_id}, order_date={record_date}, delivery_date={delivery_date}",
            )

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

# ============================================================
# [E5] 今日進貨明細 / LINE 訊息頁
# 如果之後要調整：
# 1. 顯示欄位
# 2. 店名格式
# 3. LINE 訊息文案
# 先看這一段。
# ============================================================
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
    next_day = selected_date + timedelta(days=1)
    prev_day = selected_date - timedelta(days=1)

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
# ============================================================
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
                f"<div class='order-meta'>總庫存：{total_stock_ref:g}　建議量：{suggest_qty:g}{tail}</div>",
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







