# ============================================================
# ORIVIA OMS 2.0 - 作業頁版
# 分店 -> 廠商 -> 同頁庫存/叫貨
# Google Sheets DB version
# ============================================================

from __future__ import annotations

from collections import deque
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from oms_engine import convert_to_base, convert_unit, get_base_unit

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# ============================================================
# [A1] Config
# ============================================================
DEFAULT_SHEET_ID = "1L1ogNjLWjjH8usMWC2JQowMMZkfD4zkuE-4UcgiTqXQ"  # ORIVIA_OMS_DB
LOCAL_SERVICE_ACCOUNT = "service_account.json"


# ============================================================
# [A2] Page / Global Style
# ============================================================
st.set_page_config(page_title="OMS 系統", layout="centered")


def apply_global_style():
    st.markdown(
        """
        <style>
        /* 全域表格微縮 */
        [data-testid="stTable"] td:nth-child(1),
        [data-testid="stTable"] th:nth-child(1),
        [data-testid="stDataFrame"] [role="row"] [role="gridcell"]:first-child {
            display: none !important;
        }

        [data-testid="stTable"] td,
        [data-testid="stTable"] th,
        [data-testid="stDataFrame"] [role="gridcell"],
        [data-testid="stDataFrame"] [role="columnheader"] {
            font-size: 11px !important;
            font-weight: 400 !important;
            padding: 4px 2px !important;
            line-height: 1.1 !important;
        }

        [data-testid="stTable"] th,
        [data-testid="stDataFrame"] [role="columnheader"] {
            font-weight: 600 !important;
        }

        /* number_input +/- 隱藏 */
        div[data-testid="stNumberInputStepUp"],
        div[data-testid="stNumberInputStepDown"] {
            display: none !important;
        }

        input[type=number] {
            -moz-appearance: textfield !important;
            -webkit-appearance: none !important;
            margin: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# [B1] Basic Helpers
# ============================================================
def _norm(v) -> str:
    return str(v).strip() if v is not None else ""


def _safe_float(v, default: float = 0.0) -> float:
    try:
        if v is None or str(v).strip() == "":
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    text = str(v).strip().lower()
    return text in {"true", "1", "yes", "y", "是"}


def _parse_date(v) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()

    text = str(v).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return None

    try:
        return pd.to_datetime(text).date()
    except Exception:
        return None


def _now_ts() -> str:
    return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# [B2] Google Sheets Client
# ============================================================
@st.cache_resource(show_spinner=False)
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    try:
        if "gcp" in st.secrets:
            creds = Credentials.from_service_account_info(
                dict(st.secrets["gcp"]),
                scopes=scopes,
            )
        else:
            p = Path(LOCAL_SERVICE_ACCOUNT)
            if not p.exists():
                st.error(f"找不到本機金鑰：{LOCAL_SERVICE_ACCOUNT}")
                return None
            creds = Credentials.from_service_account_file(str(p), scopes=scopes)

        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Google Sheets 連線失敗：{e}")
        return None


@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    client = get_gspread_client()
    if not client:
        return None

    try:
        sheet_id = st.secrets.get("sheet_id", DEFAULT_SHEET_ID) if hasattr(st.secrets, "get") else DEFAULT_SHEET_ID
    except Exception:
        sheet_id = DEFAULT_SHEET_ID

    try:
        return client.open_by_key(sheet_id)
    except Exception as e:
        st.error(f"開啟 Sheet 失敗：{e}")
        return None


# ============================================================
# [B3] Sheet Read / Write
# ============================================================
@st.cache_data(show_spinner=False, ttl=60)
def read_table(sheet_name: str) -> pd.DataFrame:
    sh = get_spreadsheet()
    if sh is None:
        return pd.DataFrame()

    try:
        ws = sh.worksheet(sheet_name)
        records = ws.get_all_records()
        df = pd.DataFrame(records)
        if not df.empty:
            df.columns = [_norm(c) for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()


def get_header(sheet_name: str) -> list[str]:
    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet(sheet_name)
    header = ws.row_values(1)
    if not header:
        raise ValueError(f"{sheet_name} 沒有 header")
    return [_norm(h) for h in header]


def append_row_by_header(sheet_name: str, header: list[str], row: dict):
    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet(sheet_name)
    values = [row.get(col, "") for col in header]
    ws.append_row(values, value_input_option="USER_ENTERED")


def bust_cache():
    st.cache_data.clear()


# ============================================================
# [B4] ID Sequence
# ============================================================
def _make_id(prefix: str, width: int, n: int) -> str:
    return f"{prefix}{str(n).zfill(int(width))}"


def get_next_id(key: str, env: str = "prod") -> str:
    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet("id_sequences")
    values = ws.get_all_values()
    if not values or len(values) < 2:
        raise ValueError("id_sequences 為空")

    header = [_norm(x) for x in values[0]]
    rows = values[1:]
    df = pd.DataFrame(rows, columns=header)

    hit = df[(df["key"].astype(str).str.strip() == str(key).strip()) & (df["env"].astype(str).str.strip() == str(env).strip())]
    if hit.empty:
        raise ValueError(f"id_sequences 找不到 key={key}, env={env}")

    rec = hit.iloc[0].to_dict()
    prefix = _norm(rec.get("prefix", ""))
    width = int(_safe_float(rec.get("width", 0), 0))
    next_value = int(_safe_float(rec.get("next_value", 0), 0))

    if not prefix or width <= 0 or next_value <= 0:
        raise ValueError(f"id_sequences 設定錯誤：key={key}")

    new_id = _make_id(prefix, width, next_value)

    row_index = int(hit.index[0]) + 2  # +1 header, +1 1-based
    col_next_value = header.index("next_value") + 1
    col_updated_at = header.index("updated_at") + 1 if "updated_at" in header else None

    ws.update_cell(row_index, col_next_value, str(next_value + 1))
    if col_updated_at:
        ws.update_cell(row_index, col_updated_at, _now_ts())

    bust_cache()
    return new_id


# ============================================================
# [C1] Unit Conversion (self-contained)
# ============================================================
def _filter_active_conversions(
    conversions_df: pd.DataFrame,
    item_id: str,
    as_of_date: Optional[date] = None,
) -> pd.DataFrame:
    if conversions_df is None or conversions_df.empty:
        return pd.DataFrame()

    work = conversions_df.copy()

    for col in ["item_id", "from_unit", "to_unit"]:
        if col in work.columns:
            work[col] = work[col].astype(str).str.strip()

    if "ratio" not in work.columns:
        return pd.DataFrame()

    work["ratio"] = pd.to_numeric(work["ratio"], errors="coerce")
    work = work[work["item_id"] == str(item_id).strip()]
    work = work[work["ratio"].notna()]
    work = work[work["ratio"] > 0]

    if "is_active" in work.columns:
        work = work[work["is_active"].apply(_to_bool)]

    if as_of_date is not None:
        if "effective_date" in work.columns:
            work["_eff"] = work["effective_date"].apply(_parse_date)
            work = work[work["_eff"].isna() | (work["_eff"] <= as_of_date)]
        if "end_date" in work.columns:
            work["_end"] = work["end_date"].apply(_parse_date)
            work = work[work["_end"].isna() | (work["_end"] >= as_of_date)]

    return work.copy()


def _build_unit_graph(valid_df: pd.DataFrame) -> dict:
    graph = {}

    for _, row in valid_df.iterrows():
        from_unit = _norm(row["from_unit"])
        to_unit = _norm(row["to_unit"])
        ratio = float(row["ratio"])

        if not from_unit or not to_unit or ratio <= 0:
            continue

        graph.setdefault(from_unit, []).append((to_unit, ratio))
        graph.setdefault(to_unit, []).append((from_unit, 1 / ratio))

    return graph


def get_base_unit(items_df: pd.DataFrame, item_id: str) -> str:
    if items_df.empty:
        raise ValueError("items 為空")

    work = items_df.copy()
    work["item_id"] = work["item_id"].astype(str).str.strip()

    row = work[work["item_id"] == str(item_id).strip()]
    if row.empty:
        raise ValueError(f"items 找不到 item_id={item_id}")

    base_unit = _norm(row.iloc[0].get("base_unit", ""))
    if not base_unit:
        raise ValueError(f"{item_id} 缺少 base_unit")
    return base_unit


def convert_unit(
    item_id: str,
    qty: float,
    from_unit: str,
    to_unit: str,
    conversions_df: pd.DataFrame,
    as_of_date: Optional[date] = None,
) -> float:
    item_id = _norm(item_id)
    from_unit = _norm(from_unit)
    to_unit = _norm(to_unit)

    qty = float(qty)
    if from_unit == to_unit:
        return qty

    valid_df = _filter_active_conversions(conversions_df, item_id, as_of_date)
    if valid_df.empty:
        raise ValueError(f"{item_id} 沒有有效換算規則")

    graph = _build_unit_graph(valid_df)
    if from_unit not in graph:
        raise ValueError(f"{item_id} 缺少單位 {from_unit} 的換算")
    if to_unit not in graph:
        raise ValueError(f"{item_id} 缺少單位 {to_unit} 的換算")

    queue = deque([(from_unit, 1.0)])
    visited = {from_unit}

    while queue:
        current_unit, current_factor = queue.popleft()
        if current_unit == to_unit:
            return qty * current_factor

        for next_unit, ratio in graph.get(current_unit, []):
            if next_unit not in visited:
                visited.add(next_unit)
                queue.append((next_unit, current_factor * ratio))

    raise ValueError(f"{item_id} 無法從 {from_unit} 換算到 {to_unit}")


def convert_to_base(
    item_id: str,
    qty: float,
    from_unit: str,
    items_df: pd.DataFrame,
    conversions_df: pd.DataFrame,
    as_of_date: Optional[date] = None,
):
    base_unit = get_base_unit(items_df, item_id)
    base_qty = convert_unit(
        item_id=item_id,
        qty=qty,
        from_unit=from_unit,
        to_unit=base_unit,
        conversions_df=conversions_df,
        as_of_date=as_of_date,
    )
    return base_qty, base_unit


# ============================================================
# [C2] Data Helpers
# ============================================================
def _get_active_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if "is_active" in df.columns:
        return df[df["is_active"].apply(_to_bool)].copy()
    return df.copy()


def _label_store(r) -> str:
    name = _norm(r.get("store_name_zh", "")) or _norm(r.get("store_name", ""))
    sid = _norm(r.get("store_id", ""))
    return f"{name}" if name else sid


def _label_vendor(r) -> str:
    name = _norm(r.get("vendor_name", ""))
    vid = _norm(r.get("vendor_id", ""))
    return f"{name}" if name else vid


def _get_latest_price_for_item(prices_df: pd.DataFrame, item_id: str, target_date: date) -> float:
    if prices_df.empty or "item_id" not in prices_df.columns:
        return 0.0

    tmp = prices_df.copy()
    for col in ["effective_date", "end_date", "unit_price", "is_active"]:
        if col not in tmp.columns:
            tmp[col] = ""

    tmp = tmp[tmp["item_id"].astype(str).str.strip() == str(item_id).strip()].copy()
    if tmp.empty:
        return 0.0

    tmp["__eff"] = tmp["effective_date"].apply(_parse_date)
    tmp["__end"] = tmp["end_date"].apply(_parse_date)
    tmp["__active"] = tmp["is_active"].apply(lambda x: (str(x).strip() == "" or _to_bool(x)))
    tmp["unit_price"] = pd.to_numeric(tmp["unit_price"], errors="coerce").fillna(0)

    tmp = tmp[tmp["__active"]]
    tmp = tmp[
        (tmp["__eff"].isna() | (tmp["__eff"] <= target_date))
        & (tmp["__end"].isna() | (tmp["__end"] >= target_date))
    ].copy()

    if tmp.empty:
        return 0.0

    tmp = tmp.sort_values("__eff", ascending=True)
    return float(tmp.iloc[-1]["unit_price"])


def _get_last_po_summary(
    po_df: pd.DataFrame,
    pol_df: pd.DataFrame,
    store_id: str,
    vendor_id: str,
    item_id: str,
):
    if po_df.empty or pol_df.empty:
        return 0.0, ""

    need_po = {"po_id", "store_id", "vendor_id", "order_date"}
    need_pol = {"po_id", "item_id"}
    if not need_po.issubset(set(po_df.columns)) or not need_pol.issubset(set(pol_df.columns)):
        return 0.0, ""

    po = po_df.copy()
    pol = pol_df.copy()

    po["po_id"] = po["po_id"].astype(str).str.strip()
    pol["po_id"] = pol["po_id"].astype(str).str.strip()
    pol["item_id"] = pol["item_id"].astype(str).str.strip()

    po = po[
        (po["store_id"].astype(str).str.strip() == str(store_id).strip())
        & (po["vendor_id"].astype(str).str.strip() == str(vendor_id).strip())
    ].copy()

    if po.empty:
        return 0.0, ""

    merged = pol.merge(po[["po_id", "order_date"]], on="po_id", how="inner")
    merged = merged[merged["item_id"] == str(item_id).strip()].copy()
    if merged.empty:
        return 0.0, ""

    merged["__date"] = merged["order_date"].apply(_parse_date)
    merged = merged.sort_values("__date", ascending=True)
    latest = merged.iloc[-1].to_dict()

    qty = _safe_float(latest.get("order_qty", latest.get("qty", 0)))
    unit = _norm(latest.get("order_unit", latest.get("unit_id", "")))
    return qty, unit


def _get_latest_stock_qty_in_display_unit(
    stocktakes_df: pd.DataFrame,
    stocktake_lines_df: pd.DataFrame,
    items_df: pd.DataFrame,
    conversions_df: pd.DataFrame,
    store_id: str,
    item_id: str,
    display_unit: str,
):
    if stocktakes_df.empty or stocktake_lines_df.empty:
        return 0.0

    need_st = {"stocktake_id", "store_id", "stocktake_date"}
    need_stl = {"stocktake_id", "item_id"}
    if not need_st.issubset(set(stocktakes_df.columns)) or not need_stl.issubset(set(stocktake_lines_df.columns)):
        return 0.0

    stx = stocktakes_df.copy()
    stl = stocktake_lines_df.copy()

    stx["stocktake_id"] = stx["stocktake_id"].astype(str).str.strip()
    stl["stocktake_id"] = stl["stocktake_id"].astype(str).str.strip()
    stl["item_id"] = stl["item_id"].astype(str).str.strip()

    stx = stx[stx["store_id"].astype(str).str.strip() == str(store_id).strip()].copy()
    if stx.empty:
        return 0.0

    merged = stl.merge(stx[["stocktake_id", "stocktake_date"]], on="stocktake_id", how="inner")
    merged = merged[merged["item_id"] == str(item_id).strip()].copy()
    if merged.empty:
        return 0.0

    merged["__date"] = merged["stocktake_date"].apply(_parse_date)
    merged = merged.sort_values("__date", ascending=True)
    latest = merged.iloc[-1].to_dict()

    base_qty = _safe_float(latest.get("base_qty", latest.get("stock_qty", latest.get("qty", 0))))
    if base_qty <= 0:
        return 0.0

    try:
        base_unit = get_base_unit(items_df, item_id)
        if display_unit == base_unit:
            return round(base_qty, 1)

        qty = convert_unit(
            item_id=item_id,
            qty=base_qty,
            from_unit=base_unit,
            to_unit=display_unit,
            conversions_df=conversions_df,
            as_of_date=_parse_date(latest.get("stocktake_date")),
        )
        return round(qty, 1)
    except Exception:
        return round(base_qty, 1)


# ============================================================
# [D1] Session State
# ============================================================
def init_session():
    if "step" not in st.session_state:
        st.session_state.step = "select_store"
    if "record_date" not in st.session_state:
        st.session_state.record_date = date.today()
    if "store_id" not in st.session_state:
        st.session_state.store_id = ""
    if "store_name" not in st.session_state:
        st.session_state.store_name = ""
    if "vendor_id" not in st.session_state:
        st.session_state.vendor_id = ""
    if "vendor_name" not in st.session_state:
        st.session_state.vendor_name = ""


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

    for _, row in stores_df.iterrows():
        label = _label_store(row)
        store_id = _norm(row.get("store_id", ""))
        if st.button(f"📍 {label}", key=f"store_{store_id}", use_container_width=True):
            st.session_state.store_id = store_id
            st.session_state.store_name = label
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
    if vendors_df.empty:
        st.warning("⚠️ 廠商資料讀取失敗")
        return

    vendors = vendors_df.sort_values(by=["vendor_name"], ascending=True).reset_index(drop=True)

    for i in range(0, len(vendors), 2):
        cols = st.columns(2)

        left = vendors.iloc[i]
        with cols[0]:
            if st.button(f"📦 {_label_vendor(left)}", key=f"vendor_{left.get('vendor_id','')}", use_container_width=True):
                st.session_state.vendor_id = _norm(left.get("vendor_id", ""))
                st.session_state.vendor_name = _label_vendor(left)
                st.session_state.step = "order_entry"
                st.rerun()

        if i + 1 < len(vendors):
            right = vendors.iloc[i + 1]
            with cols[1]:
                if st.button(f"📦 {_label_vendor(right)}", key=f"vendor_{right.get('vendor_id','')}", use_container_width=True):
                    st.session_state.vendor_id = _norm(right.get("vendor_id", ""))
                    st.session_state.vendor_name = _label_vendor(right)
                    st.session_state.step = "order_entry"
                    st.rerun()

    if st.button("⬅️ 返回分店列表", use_container_width=True):
        st.session_state.step = "select_store"
        st.rerun()


# ============================================================
# [E3] Order Entry - 同頁庫存 / 叫貨
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

    def _item_display_name(r) -> str:
        return _norm(r.get("item_name_zh", "")) or _norm(r.get("item_name", ""))

    vendor_items["_display_name"] = vendor_items.apply(_item_display_name, axis=1)
    vendor_items = vendor_items.sort_values(by=["_display_name"], ascending=True)

    # ------------------------------------------------------------
    # 上次叫貨
    # ------------------------------------------------------------
    def _get_last_po_summary(
        po_df: pd.DataFrame,
        pol_df: pd.DataFrame,
        store_id: str,
        vendor_id: str,
        item_id: str,
    ):
        if po_df.empty or pol_df.empty:
            return 0.0, ""

        need_po = {"po_id", "store_id", "vendor_id", "order_date"}
        need_pol = {"po_id", "item_id"}
        if not need_po.issubset(set(po_df.columns)) or not need_pol.issubset(set(pol_df.columns)):
            return 0.0, ""

        po = po_df.copy()
        pol = pol_df.copy()

        po["po_id"] = po["po_id"].astype(str).str.strip()
        pol["po_id"] = pol["po_id"].astype(str).str.strip()
        pol["item_id"] = pol["item_id"].astype(str).str.strip()

        po = po[
            (po["store_id"].astype(str).str.strip() == str(store_id).strip())
            & (po["vendor_id"].astype(str).str.strip() == str(vendor_id).strip())
        ].copy()

        if po.empty:
            return 0.0, ""

        merged = pol.merge(po[["po_id", "order_date"]], on="po_id", how="inner")
        merged = merged[merged["item_id"] == str(item_id).strip()].copy()

        if merged.empty:
            return 0.0, ""

        merged["__date"] = merged["order_date"].apply(_parse_date)
        merged = merged.sort_values("__date", ascending=True)
        latest = merged.iloc[-1].to_dict()

        qty = _safe_float(latest.get("order_qty", latest.get("qty", 0)))
        unit = _norm(latest.get("order_unit", latest.get("unit_id", "")))
        return qty, unit

    # ------------------------------------------------------------
    # 目前庫存（抓最近一次盤點，轉成 default_stock_unit 顯示）
    # ------------------------------------------------------------
    def _get_latest_stock_qty_in_display_unit(
        stocktakes_df: pd.DataFrame,
        stocktake_lines_df: pd.DataFrame,
        items_df: pd.DataFrame,
        conversions_df: pd.DataFrame,
        store_id: str,
        item_id: str,
        display_unit: str,
    ):
        if stocktakes_df.empty or stocktake_lines_df.empty:
            return 0.0

        need_st = {"stocktake_id", "store_id", "stocktake_date"}
        need_stl = {"stocktake_id", "item_id"}
        if not need_st.issubset(set(stocktakes_df.columns)) or not need_stl.issubset(set(stocktake_lines_df.columns)):
            return 0.0

        stx = stocktakes_df.copy()
        stl = stocktake_lines_df.copy()

        stx["stocktake_id"] = stx["stocktake_id"].astype(str).str.strip()
        stl["stocktake_id"] = stl["stocktake_id"].astype(str).str.strip()
        stl["item_id"] = stl["item_id"].astype(str).str.strip()

        stx = stx[stx["store_id"].astype(str).str.strip() == str(store_id).strip()].copy()
        if stx.empty:
            return 0.0

        merged = stl.merge(stx[["stocktake_id", "stocktake_date"]], on="stocktake_id", how="inner")
        merged = merged[merged["item_id"] == str(item_id).strip()].copy()
        if merged.empty:
            return 0.0

        merged["__date"] = merged["stocktake_date"].apply(_parse_date)
        merged = merged.sort_values("__date", ascending=True)
        latest = merged.iloc[-1].to_dict()

        base_qty = _safe_float(latest.get("base_qty", 0))
        base_unit = _norm(latest.get("base_unit", ""))

        # 舊資料可能還沒有 base_qty / base_unit，就從原始值轉
        if base_qty <= 0 or not base_unit:
            raw_qty = _safe_float(latest.get("stock_qty", latest.get("qty", 0)))
            raw_unit = _norm(latest.get("stock_unit", latest.get("unit_id", "")))

            if raw_qty <= 0 or not raw_unit:
                return 0.0

            try:
                base_qty, base_unit = convert_to_base(
                    item_id=item_id,
                    qty=raw_qty,
                    from_unit=raw_unit,
                    items_df=items_df,
                    conversions_df=conversions_df,
                    as_of_date=_parse_date(latest.get("stocktake_date")),
                )
            except Exception:
                return round(raw_qty, 1)

        try:
            if display_unit == base_unit:
                return round(base_qty, 1)

            qty = convert_unit(
                item_id=item_id,
                qty=base_qty,
                from_unit=base_unit,
                to_unit=display_unit,
                conversions_df=conversions_df,
                as_of_date=_parse_date(latest.get("stocktake_date")),
            )
            return round(qty, 1)
        except Exception:
            return round(base_qty, 1)

    # ------------------------------------------------------------
    # 價格
    # ------------------------------------------------------------
    def _get_latest_price_for_item(prices_df: pd.DataFrame, item_id: str, target_date: date) -> float:
        if prices_df.empty or "item_id" not in prices_df.columns:
            return 0.0

        tmp = prices_df.copy()
        for col in ["effective_date", "end_date", "unit_price", "is_active"]:
            if col not in tmp.columns:
                tmp[col] = ""

        tmp = tmp[tmp["item_id"].astype(str).str.strip() == str(item_id).strip()].copy()
        if tmp.empty:
            return 0.0

        tmp["__eff"] = tmp["effective_date"].apply(_parse_date)
        tmp["__end"] = tmp["end_date"].apply(_parse_date)
        tmp["__active"] = tmp["is_active"].apply(lambda x: (str(x).strip() == "" or _to_bool(x)))
        tmp["unit_price"] = pd.to_numeric(tmp["unit_price"], errors="coerce").fillna(0)

        tmp = tmp[tmp["__active"]]
        tmp = tmp[
            (tmp["__eff"].isna() | (tmp["__eff"] <= target_date))
            & (tmp["__end"].isna() | (tmp["__end"] >= target_date))
        ].copy()

        if tmp.empty:
            return 0.0

        tmp = tmp.sort_values("__eff", ascending=True)
        return float(tmp.iloc[-1]["unit_price"])

    # ------------------------------------------------------------
    # 參考資料
    # ------------------------------------------------------------
    ref_rows = []
    item_meta = {}

    for _, row in vendor_items.iterrows():
        item_id = _norm(row.get("item_id", ""))
        item_name = _item_display_name(row)

        base_unit = _norm(row.get("base_unit", ""))
        stock_unit = _norm(row.get("default_stock_unit", "")) or base_unit
        order_unit = _norm(row.get("default_order_unit", "")) or base_unit
        price = _get_latest_price_for_item(prices_df, item_id, st.session_state.record_date)

        last_order_qty, _ = _get_last_po_summary(
            po_df=po_df,
            pol_df=pol_df,
            store_id=st.session_state.store_id,
            vendor_id=st.session_state.vendor_id,
            item_id=item_id,
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

        ref_rows.append(
            {
                "品項名稱": item_name,
                "上次叫貨": round(last_order_qty, 1),
                "目前庫存": round(current_stock_qty, 1),
            }
        )

        item_meta[item_id] = {
            "item_name": item_name,
            "base_unit": base_unit,
            "stock_unit": stock_unit,
            "order_unit": order_unit,
            "price": round(price, 1),
            "current_stock_qty": round(current_stock_qty, 1),
            "suggest_qty": 0.0,
        }

    ref_df = pd.DataFrame(ref_rows)
    ref_df = ref_df[(ref_df["上次叫貨"] > 0) | (ref_df["目前庫存"] > 0)].copy()

    with st.expander("📊 查看上次叫貨 / 庫存參考（已自動隱藏無紀錄品項）", expanded=False):
        if ref_df.empty:
            st.caption("目前沒有可參考的資料")
        else:
            for col in ["上次叫貨", "目前庫存"]:
                ref_df[col] = ref_df[col].map(lambda x: f"{x:.1f}")
            st.table(ref_df)

    st.markdown("<div class='order-divider'></div>", unsafe_allow_html=True)

    h1, h2, h3 = st.columns([6, 1, 1])
    h1.write("**品項名稱**")
    h2.write("<div style='text-align:center;'><b>庫</b></div>", unsafe_allow_html=True)
    h3.write("<div style='text-align:center;'><b>進</b></div>", unsafe_allow_html=True)

    with st.form("order_entry_form"):
        submit_rows = []

        for _, row in vendor_items.iterrows():
            item_id = _norm(row.get("item_id", ""))
            meta = item_meta[item_id]

            item_name = meta["item_name"]
            stock_unit = meta["stock_unit"]
            order_unit = meta["order_unit"]
            current_stock_qty = _safe_float(meta["current_stock_qty"])
            price = _safe_float(meta["price"])
            suggest_qty = _safe_float(meta["suggest_qty"])

            c1, c2, c3 = st.columns([6, 1, 1])

            with c1:
                st.write(f"<b>{item_name}</b>", unsafe_allow_html=True)
                st.caption(f"{stock_unit} (前結:{current_stock_qty:.1f} | 單價:{price:.1f} | 💡建議:{suggest_qty:.1f})")

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
                st.caption(base_unit)   # ⭐ 庫存欄下方小字，固定顯示基準單位
            
            with c3:
                order_input = st.number_input(...)
                st.caption(order_unit)
            
                if st.button("單位", key=f"btn_unit_{item_id}"):
                    st.session_state[f"show_unit_{item_id}"] = not st.session_state.get(f"show_unit_{item_id}", False)
            
                if st.session_state.get(f"show_unit_{item_id}", False):
                    selected_unit = st.selectbox(
                        "選單位",
                        options=orderable_unit_options,
                        key=f"select_unit_{item_id}",
                        label_visibility="collapsed",
                    )
                st.caption(order_unit)  # ⭐ 進貨欄下方小字，顯示目前叫貨單位
    
            submit_rows.append(
                {
                    "item_id": item_id,
                    "item_name": item_name,
                    "stock_qty": float(stock_input),
                    "stock_unit": stock_unit,
                    "order_qty": float(order_input),
                    "order_unit": order_unit,
                    "unit_price": float(price),
                }
            )

        submitted = st.form_submit_button("💾 儲存庫存並同步叫貨", use_container_width=True)

    if submitted:
        stocktake_header = get_header("stocktakes")
        stl_header = get_header("stocktake_lines")

        stocktake_id = get_next_id("stocktakes")
        now = _now_ts()

        stocktake_row = {c: "" for c in stocktake_header}
        defaults_stocktake = {
            "stocktake_id": stocktake_id,
            "store_id": st.session_state.store_id,
            "stocktake_date": str(st.session_state.record_date),
            "status": "done",
            "note": f"vendor={st.session_state.vendor_id}",
            "created_at": now,
            "created_by": "SYSTEM",
            "updated_at": "",
            "updated_by": "",
        }
        for k, v in defaults_stocktake.items():
            if k in stocktake_row:
                stocktake_row[k] = v

        append_row_by_header("stocktakes", stocktake_header, stocktake_row)

        # 只寫入有變動的庫存
        for r in submit_rows:
            if abs(r["stock_qty"] - item_meta[r["item_id"]]["current_stock_qty"]) < 0.0001:
                continue

            stocktake_line_id = get_next_id("stocktake_lines")

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

            line_row = {c: "" for c in stl_header}
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
                if k in line_row:
                    line_row[k] = v

            append_row_by_header("stocktake_lines", stl_header, line_row)

        # 只寫入有叫貨的品項
        order_rows = [r for r in submit_rows if r["order_qty"] > 0]
        po_id = ""

        if order_rows:
            po_header = get_header("purchase_orders")
            pol_header = get_header("purchase_order_lines")

            po_id = get_next_id("purchase_orders")
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

            append_row_by_header("purchase_orders", po_header, po_row)

            for r in order_rows:
                po_line_id = get_next_id("purchase_order_lines")

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

                pol_row = {c: "" for c in pol_header}
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
                    if k in pol_row:
                        pol_row[k] = v

                append_row_by_header("purchase_order_lines", pol_header, pol_row)

        bust_cache()
        st.success(f"✅ 已儲存庫存；{('並建立叫貨單：' + po_id) if po_id else '本次無叫貨品項'}")

        if st.button("返回廠商列表", use_container_width=True):
            st.session_state.step = "select_vendor"
            st.rerun()

    if st.button("⬅️ 返回功能選單", use_container_width=True, key="back_from_order_entry"):
        st.session_state.step = "select_vendor"
        st.rerun()


# ============================================================
# [F1] Router
# ============================================================
def router():
    step = st.session_state.step

    if step == "select_store":
        page_select_store()
    elif step == "select_vendor":
        page_select_vendor()
    elif step == "order_entry":
        page_order_entry()


# ============================================================
# [G1] Main
# ============================================================
def main():
    apply_global_style()
    init_session()
    router()


if __name__ == "__main__":
    main()











