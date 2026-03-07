# ============================================================
# ORIVIA OMS 1.0 外觀 + OMS 2.0 資料庫（穩定版）
# Google Sheets DB version
# ============================================================

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

from oms_engine import convert_to_base, convert_unit, get_base_unit

# Plotly (optional)
try:
    import plotly.express as px
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False


# ============================================================
# [A1] Config
# ============================================================
DEFAULT_SHEET_ID = "1L1ogNjLWjjH8usMWC2JQowMMZkfD4zkuE-4UcgiTqXQ"
LOCAL_SERVICE_ACCOUNT = Path("service_account.json")

PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "scrollZoom": False,
    "doubleClick": False,
    "editable": False,
    "modeBarButtonsToRemove": [
        "zoom2d",
        "pan2d",
        "select2d",
        "lasso2d",
        "zoomIn2d",
        "zoomOut2d",
        "autoScale2d",
        "resetScale2d",
        "hoverClosestCartesian",
        "hoverCompareCartesian",
        "toggleSpikelines",
    ],
}

st.set_page_config(page_title="OMS 系統", layout="centered")


# ============================================================
# [A2] Global UI Style
# ============================================================
def apply_global_style():
    st.markdown(
        """
        <style>
        /* 移除表格最左側序號 */
        [data-testid="stTable"] td:nth-child(1),
        [data-testid="stTable"] th:nth-child(1),
        [data-testid="stDataFrame"] [role="row"] [role="gridcell"]:first-child {
            display: none !important;
        }

        /* 表格微縮 */
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

        /* 隱藏 number_input +/- */
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


def _get_secret_sheet_id() -> str:
    try:
        if hasattr(st.secrets, "get"):
            return st.secrets.get("sheet_id", DEFAULT_SHEET_ID)
    except Exception:
        pass
    return DEFAULT_SHEET_ID


def _parse_vendor_id_from_note(note: str) -> str:
    text = _norm(note)
    if "vendor=" not in text:
        return ""
    try:
        return text.split("vendor=", 1)[1].strip()
    except Exception:
        return ""


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
            if not LOCAL_SERVICE_ACCOUNT.exists():
                st.error(f"找不到本機金鑰：{LOCAL_SERVICE_ACCOUNT}")
                return None
            creds = Credentials.from_service_account_file(
                str(LOCAL_SERVICE_ACCOUNT),
                scopes=scopes,
            )

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
        return client.open_by_key(_get_secret_sheet_id())
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
    except Exception as e:
        st.warning(f"{sheet_name} 讀取失敗：{e}")
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
    read_table.clear()


# ============================================================
# [B4] LINE Push
# ============================================================
def send_line_message(message: str) -> bool:
    import json
    import requests

    try:
        token = st.secrets["line_bot"]["channel_access_token"]
        current_store_id = st.session_state.get("store_id", "")
        target_id = st.secrets.get("line_groups", {}).get(current_store_id)

        if not target_id:
            target_id = st.secrets["line_bot"].get("user_id")

        if not target_id:
            return False

        url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        payload = {
            "to": target_id,
            "messages": [{"type": "text", "text": message}],
        }

        response = requests.post(url, headers=headers, data=json.dumps(payload))
        return response.status_code == 200
    except Exception:
        return False


# ============================================================
# [B5] ID Sequence
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

    for col in ["key", "env", "prefix", "width", "next_value"]:
        if col not in df.columns:
            raise ValueError(f"id_sequences 缺少欄位：{col}")

    hit = df[
        (df["key"].astype(str).str.strip() == str(key).strip())
        & (df["env"].astype(str).str.strip() == str(env).strip())
    ]
    if hit.empty:
        raise ValueError(f"id_sequences 找不到 key={key}, env={env}")

    rec = hit.iloc[0].to_dict()
    prefix = _norm(rec.get("prefix", ""))
    width = int(_safe_float(rec.get("width", 0), 0))
    next_value = int(_safe_float(rec.get("next_value", 0), 0))

    if not prefix or width <= 0 or next_value <= 0:
        raise ValueError(f"id_sequences 設定錯誤：key={key}")

    new_id = _make_id(prefix, width, next_value)

    row_index = int(hit.index[0]) + 2
    col_next_value = header.index("next_value") + 1
    col_updated_at = header.index("updated_at") + 1 if "updated_at" in header else None

    ws.update_cell(row_index, col_next_value, str(next_value + 1))
    if col_updated_at:
        ws.update_cell(row_index, col_updated_at, _now_ts())

    bust_cache()
    return new_id


# ============================================================
# [C1] Data Helpers
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
    return name if name else sid


def _label_vendor(r) -> str:
    name = _norm(r.get("vendor_name", ""))
    vid = _norm(r.get("vendor_id", ""))
    return name if name else vid


def _item_display_name(r) -> str:
    return _norm(r.get("item_name_zh", "")) or _norm(r.get("item_name", ""))


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


def _coalesce_columns(df: pd.DataFrame, candidates: list[str], default="") -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype="object")

    result = pd.Series([pd.NA] * len(df), index=df.index, dtype="object")

    for col in candidates:
        if col in df.columns:
            s = df[col].copy()
            s = s.where(~pd.isna(s), pd.NA)

            if s.dtype == "object":
                s = s.apply(lambda x: pd.NA if str(x).strip() == "" else x)

            result = result.combine_first(s)

    if default != "":
        result = result.fillna(default)

    return result
    
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


def _build_purchase_detail_df() -> pd.DataFrame:
    po_df = read_table("purchase_orders")
    pol_df = read_table("purchase_order_lines")
    vendors_df = read_table("vendors")
    items_df = read_table("items")
    stores_df = read_table("stores")

    if po_df.empty or pol_df.empty:
        return pd.DataFrame()

    po = po_df.copy()
    pol = pol_df.copy()

    if "po_id" not in po.columns or "po_id" not in pol.columns:
        return pd.DataFrame()

    po["po_id"] = po["po_id"].astype(str).str.strip()
    pol["po_id"] = pol["po_id"].astype(str).str.strip()

    if "item_id" in pol.columns:
        pol["item_id"] = pol["item_id"].astype(str).str.strip()
    else:
        pol["item_id"] = ""

    po_keep = po.copy()
    rename_map = {}
    if "store_id" in po_keep.columns:
        rename_map["store_id"] = "po_store_id"
    if "vendor_id" in po_keep.columns:
        rename_map["vendor_id"] = "po_vendor_id"
    if "order_date" in po_keep.columns:
        rename_map["order_date"] = "po_order_date"
    if "status" in po_keep.columns:
        rename_map["status"] = "po_status"

    po_keep = po_keep.rename(columns=rename_map)

    keep_cols = ["po_id"]
    for c in ["po_store_id", "po_vendor_id", "po_order_date", "po_status"]:
        if c in po_keep.columns:
            keep_cols.append(c)

    merged = pol.merge(po_keep[keep_cols], on="po_id", how="left")

    merged["store_id"] = _coalesce_columns(merged, ["po_store_id", "store_id"], default="")
    merged["vendor_id"] = _coalesce_columns(merged, ["po_vendor_id", "vendor_id"], default="")
    merged["order_date"] = _coalesce_columns(merged, ["po_order_date", "order_date"], default="")
    merged["status"] = _coalesce_columns(merged, ["po_status", "status"], default="")

    if not vendors_df.empty and "vendor_id" in vendors_df.columns:
        v = vendors_df.copy()
        v["vendor_id"] = v["vendor_id"].astype(str).str.strip()
        v["vendor_name_disp"] = v.apply(_label_vendor, axis=1)
        merged = merged.merge(v[["vendor_id", "vendor_name_disp"]], on="vendor_id", how="left")
    else:
        merged["vendor_name_disp"] = merged["vendor_id"]

    if not items_df.empty and "item_id" in items_df.columns:
        i = items_df.copy()
        i["item_id"] = i["item_id"].astype(str).str.strip()
        i["item_name_disp"] = i.apply(_item_display_name, axis=1)

        keep_item_cols = ["item_id", "item_name_disp"]
        for c in ["base_unit", "default_vendor_id", "default_stock_unit"]:
            if c in i.columns:
                keep_item_cols.append(c)

        merged = merged.merge(i[keep_item_cols], on="item_id", how="left")
    else:
        merged["item_name_disp"] = merged["item_id"]

    if not stores_df.empty and "store_id" in stores_df.columns:
        s = stores_df.copy()
        s["store_id"] = s["store_id"].astype(str).str.strip()
        s["store_name_disp"] = s.apply(_label_store, axis=1)
        merged = merged.merge(s[["store_id", "store_name_disp"]], on="store_id", how="left")
    else:
        merged["store_name_disp"] = merged["store_id"]

    merged["order_date_dt"] = merged["order_date"].apply(_parse_date)

    merged["order_qty_num"] = pd.to_numeric(
        _coalesce_columns(merged, ["order_qty", "qty"], default=0),
        errors="coerce"
    ).fillna(0)

    merged["unit_price_num"] = pd.to_numeric(
        _coalesce_columns(merged, ["unit_price"], default=0),
        errors="coerce"
    ).fillna(0)

    if "line_amount" in merged.columns:
        merged["amount_num"] = pd.to_numeric(merged["line_amount"], errors="coerce").fillna(0)
    elif "amount" in merged.columns:
        merged["amount_num"] = pd.to_numeric(merged["amount"], errors="coerce").fillna(0)
    else:
        merged["amount_num"] = merged["order_qty_num"] * merged["unit_price_num"]

    merged["order_unit_disp"] = _coalesce_columns(merged, ["order_unit", "unit_id"], default="").astype(str).str.strip()

    return merged.copy()

def _build_stock_detail_df() -> pd.DataFrame:
    st_df = read_table("stocktakes")
    stl_df = read_table("stocktake_lines")
    items_df = read_table("items")
    vendors_df = read_table("vendors")
    stores_df = read_table("stores")
    conversions_df = _get_active_df(read_table("unit_conversions"))

    if st_df.empty or stl_df.empty:
        return pd.DataFrame()

    stx = st_df.copy()
    stl = stl_df.copy()

    if "stocktake_id" not in stx.columns or "stocktake_id" not in stl.columns:
        return pd.DataFrame()

    stx["stocktake_id"] = stx["stocktake_id"].astype(str).str.strip()
    stl["stocktake_id"] = stl["stocktake_id"].astype(str).str.strip()

    if "item_id" in stl.columns:
        stl["item_id"] = stl["item_id"].astype(str).str.strip()
    else:
        stl["item_id"] = ""

    st_keep = stx.copy()
    rename_map = {}
    if "store_id" in st_keep.columns:
        rename_map["store_id"] = "st_store_id"
    if "stocktake_date" in st_keep.columns:
        rename_map["stocktake_date"] = "st_stocktake_date"
    if "note" in st_keep.columns:
        rename_map["note"] = "st_note"

    st_keep = st_keep.rename(columns=rename_map)

    keep_cols = ["stocktake_id"]
    for c in ["st_store_id", "st_stocktake_date", "st_note"]:
        if c in st_keep.columns:
            keep_cols.append(c)

    merged = stl.merge(st_keep[keep_cols], on="stocktake_id", how="left")

    merged["store_id"] = _coalesce_columns(merged, ["st_store_id", "store_id"], default="")
    merged["stocktake_date"] = _coalesce_columns(merged, ["st_stocktake_date", "stocktake_date"], default="")
    merged["note_for_parse"] = _coalesce_columns(merged, ["st_note", "note"], default="")
    merged["vendor_id"] = _coalesce_columns(merged, ["vendor_id"], default="")

    merged["vendor_id"] = merged["vendor_id"].where(
        merged["vendor_id"].astype(str).str.strip() != "",
        merged["note_for_parse"].apply(_parse_vendor_id_from_note),
    )

    if not items_df.empty and "item_id" in items_df.columns:
        i = items_df.copy()
        i["item_id"] = i["item_id"].astype(str).str.strip()
        i["item_name_disp"] = i.apply(_item_display_name, axis=1)

        keep_item_cols = ["item_id", "item_name_disp"]
        for c in ["base_unit", "default_vendor_id", "default_stock_unit"]:
            if c in i.columns:
                keep_item_cols.append(c)

        merged = merged.merge(i[keep_item_cols], on="item_id", how="left")

        if "default_vendor_id" in merged.columns:
            merged["vendor_id"] = merged["vendor_id"].where(
                merged["vendor_id"].astype(str).str.strip() != "",
                merged["default_vendor_id"],
            )
    else:
        merged["item_name_disp"] = merged["item_id"]

    if not vendors_df.empty and "vendor_id" in vendors_df.columns:
        v = vendors_df.copy()
        v["vendor_id"] = v["vendor_id"].astype(str).str.strip()
        v["vendor_name_disp"] = v.apply(_label_vendor, axis=1)
        merged = merged.merge(v[["vendor_id", "vendor_name_disp"]], on="vendor_id", how="left")
    else:
        merged["vendor_name_disp"] = merged["vendor_id"]

    if not stores_df.empty and "store_id" in stores_df.columns:
        s = stores_df.copy()
        s["store_id"] = s["store_id"].astype(str).str.strip()
        s["store_name_disp"] = s.apply(_label_store, axis=1)
        merged = merged.merge(s[["store_id", "store_name_disp"]], on="store_id", how="left")
    else:
        merged["store_name_disp"] = merged["store_id"]

    merged["stocktake_date_dt"] = merged["stocktake_date"].apply(_parse_date)

    merged["base_qty_num"] = pd.to_numeric(
        _coalesce_columns(merged, ["base_qty", "stock_qty", "qty"], default=0),
        errors="coerce"
    ).fillna(0)

    def _display_stock_qty(row):
        item_id = _norm(row.get("item_id", ""))
        if not item_id:
            return round(_safe_float(row.get("base_qty_num", 0)), 1)

        display_unit = _norm(row.get("default_stock_unit", "")) or _norm(row.get("base_unit", ""))
        if not display_unit:
            return round(_safe_float(row.get("base_qty_num", 0)), 1)

        try:
            base_unit = _norm(row.get("base_unit", ""))
            base_qty = _safe_float(row.get("base_qty_num", 0))
            if not base_unit or base_qty == 0:
                return round(base_qty, 1)
            if display_unit == base_unit:
                return round(base_qty, 1)

            return round(
                convert_unit(
                    item_id=item_id,
                    qty=base_qty,
                    from_unit=base_unit,
                    to_unit=display_unit,
                    conversions_df=conversions_df,
                    as_of_date=row.get("stocktake_date_dt"),
                ),
                1,
            )
        except Exception:
            return round(_safe_float(row.get("base_qty_num", 0)), 1)

    merged["display_stock_qty"] = merged.apply(_display_stock_qty, axis=1)

    if "default_stock_unit" in merged.columns:
        merged["display_stock_unit"] = merged["default_stock_unit"].where(
            merged["default_stock_unit"].astype(str).str.strip() != "",
            merged["base_unit"],
        )
    else:
        merged["display_stock_unit"] = merged["base_unit"]

    return merged.copy()


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
# [E1] select_store - 分店選擇頁
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
            st.session_state.step = "select_vendor"
            st.rerun()


# ============================================================
# [E2] select_vendor - 廠商與功能中心
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

    item_vendor_ids = set(items_df.get("default_vendor_id", pd.Series(dtype=str)).astype(str).str.strip())
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
            if st.button(
                f"📦 {left['vendor_label']}",
                key=f"vendor_{left.get('vendor_id','')}",
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
                    key=f"vendor_{right.get('vendor_id','')}",
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
# [E3] order_entry - 同頁庫存 / 叫貨
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
        items_df["default_vendor_id"].astype(str).str.strip()
        == str(st.session_state.vendor_id).strip()
    ].copy()

    if vendor_items.empty:
        st.info("💡 此廠商目前沒有對應品項")
        if st.button("⬅️ 返回功能選單", use_container_width=True):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    vendor_items["_display_name"] = vendor_items.apply(_item_display_name, axis=1)
    vendor_items = vendor_items.sort_values(by=["_display_name"], ascending=True)

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
            "suggest_qty": 0.0,
        }

    ref_df = pd.DataFrame(ref_rows)
    if not ref_df.empty:
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
            base_unit = meta["base_unit"]
            stock_unit = base_unit
            order_unit = meta["order_unit"]
            current_stock_qty = _safe_float(meta["current_stock_qty"])
            price = _safe_float(meta["price"])
            suggest_qty = _safe_float(meta["suggest_qty"])

            c1, c2, c3 = st.columns([6, 1, 1])

            with c1:
                st.write(f"<b>{item_name}</b>", unsafe_allow_html=True)
                st.caption(
                    f"{base_unit} (前結:{current_stock_qty:.1f} | 單價:{price:.1f} | 💡建議:{suggest_qty:.1f})"
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

            orderable_unit_options = meta["orderable_unit_options"]

            with c3:
                order_input = st.number_input(
                    "進",
                    min_value=0.0,
                    step=0.1,
                    format="%.1f",
                    value=float(suggest_qty),
                    key=f"order_{item_id}",
                    label_visibility="collapsed",
                )
                selected_order_unit = st.selectbox(
                    "進貨單位",
                    options=orderable_unit_options,
                    index=orderable_unit_options.index(order_unit) if order_unit in orderable_unit_options else 0,
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
                    "unit_price": float(price),
                }
            )

        submitted = st.form_submit_button("💾 儲存庫存並同步叫貨", use_container_width=True)

    if submitted:
        try:
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
            bust_cache()
            st.success(f"✅ 已儲存庫存；{('並建立叫貨單：' + po_id) if po_id else '本次無叫貨品項'}")
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
# [E4] view_history - 歷史紀錄查詢
# ============================================================
def page_view_history():
    st.markdown(
        """
        <style>
        [data-testid='stMainBlockContainer'] {
            max-width: 95% !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        [data-testid='stDataFrame'] [role='gridcell'] {
            padding: 1px 2px !important;
            line-height: 1.0 !important;
        }
        [data-testid='stDataFrame'] [role='columnheader'] {
            padding: 2px 2px !important;
            font-size: 10px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title(f"📜 {st.session_state.store_name} 歷史紀錄")

    stock_df = _build_stock_detail_df()
    po_df = _build_purchase_detail_df()

    c_h_date1, c_h_date2 = st.columns(2)
    h_start = c_h_date1.date_input("起始日期", value=date.today() - timedelta(days=7), key="h_start")
    h_end = c_h_date2.date_input("結束日期", value=date.today(), key="h_end")

    t1, t2 = st.tabs(["📋 明細", "📈 趨勢"])

    with t1:
        detail_rows = []

        if not stock_df.empty and "store_id" in stock_df.columns:
            stock_work = stock_df[
                stock_df["store_id"].astype(str).str.strip() == str(st.session_state.store_id).strip()
            ].copy()

            if "stocktake_date_dt" in stock_work.columns:
                stock_work = stock_work[
                    stock_work["stocktake_date_dt"].notna()
                    & (stock_work["stocktake_date_dt"] >= h_start)
                    & (stock_work["stocktake_date_dt"] <= h_end)
                ].copy()

                for _, r in stock_work.iterrows():
                    detail_rows.append(
                        {
                            "日期": r.get("stocktake_date_dt"),
                            "類型": "庫存",
                            "廠商": _norm(r.get("vendor_name_disp", "")) or "未指定",
                            "品項名稱": _norm(r.get("item_name_disp", "")),
                            "數量": round(_safe_float(r.get("display_stock_qty", 0)), 1),
                            "單位": _norm(r.get("display_stock_unit", "")),
                            "單價": "",
                            "金額": "",
                        }
                    )

        if not po_df.empty and "store_id" in po_df.columns:
            po_work = po_df[
                po_df["store_id"].astype(str).str.strip() == str(st.session_state.store_id).strip()
            ].copy()

            if "order_date_dt" in po_work.columns:
                po_work = po_work[
                    po_work["order_date_dt"].notna()
                    & (po_work["order_date_dt"] >= h_start)
                    & (po_work["order_date_dt"] <= h_end)
                ].copy()

                for _, r in po_work.iterrows():
                    detail_rows.append(
                        {
                            "日期": r.get("order_date_dt"),
                            "類型": "叫貨",
                            "廠商": _norm(r.get("vendor_name_disp", "")) or "未指定",
                            "品項名稱": _norm(r.get("item_name_disp", "")),
                            "數量": round(_safe_float(r.get("order_qty_num", 0)), 1),
                            "單位": _norm(r.get("order_unit_disp", "")),
                            "單價": round(_safe_float(r.get("unit_price_num", 0)), 1),
                            "金額": round(_safe_float(r.get("amount_num", 0)), 1),
                        }
                    )

        detail_df = pd.DataFrame(detail_rows)

        if detail_df.empty:
            st.info("💡 此區間內無紀錄。")
        else:
            col_v, col_i = st.columns(2)
        
            all_v = ["全部廠商"] + sorted(
                [
                    x for x in detail_df["廠商"].dropna().unique().tolist()
                    if str(x).strip() and str(x).strip().lower() != "nan"
                ]
            )
        
            sel_v = col_v.selectbox(
                "📦 1. 選擇廠商",
                options=all_v,
                index=0,
                key="hist_vendor"
            )
        
            filt_df = detail_df.copy()
            if sel_v != "全部廠商":
                filt_df = filt_df[filt_df["廠商"] == sel_v]
        
            all_i = ["全部品項"] + sorted(
                [
                    x for x in filt_df["品項名稱"].dropna().unique().tolist()
                    if str(x).strip() and str(x).strip().lower() != "nan"
                ]
            )
        
            sel_i = col_i.selectbox(
                "🏷️ 2. 選擇品項",
                options=all_i,
                index=0,
                key="hist_item"
            )
        
            if sel_i != "全部品項":
                filt_df = filt_df[filt_df["品項名稱"] == sel_i]

    filt_df["顯示日期"] = pd.to_datetime(filt_df["日期"]).dt.strftime("%m-%d")
    filt_df = filt_df.sort_values(["日期", "類型"], ascending=[False, True])
            show_cols = ["顯示日期", "類型", "廠商", "品項名稱", "數量", "單位", "單價", "金額"]
            st.dataframe(
                filt_df[show_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "顯示日期": st.column_config.TextColumn("日期", width="small"),
                    "類型": st.column_config.TextColumn(width="small"),
                    "廠商": st.column_config.TextColumn(width="small"),
                    "品項名稱": st.column_config.TextColumn(width="medium"),
                    "數量": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "單位": st.column_config.TextColumn(width="small"),
                    "單價": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "金額": st.column_config.NumberColumn(format="%.1f", width="small"),
                },
            )

    with t2:
        if not HAS_PLOTLY:
            st.info("💡 Plotly 未安裝，無法顯示趨勢圖。")
        else:
            if po_df.empty or "store_id" not in po_df.columns or "order_date_dt" not in po_df.columns:
                st.info("💡 此區間內無叫貨趨勢資料。")
            else:
                po_work = po_df[
                    po_df["store_id"].astype(str).str.strip() == str(st.session_state.store_id).strip()
                ].copy()

                po_work = po_work[
                    po_work["order_date_dt"].notna()
                    & (po_work["order_date_dt"] >= h_start)
                    & (po_work["order_date_dt"] <= h_end)
                ].copy()

                if po_work.empty:
                    st.info("💡 此區間內無叫貨趨勢資料。")
                else:
                    col_v2, col_i2 = st.columns(2)
                    all_v2 = sorted(
                        [x for x in po_work["vendor_name_disp"].dropna().unique().tolist() if str(x).strip()]
                    )

                    if not all_v2:
                        st.info("💡 此區間內無廠商資料。")
                    else:
                        sel_v2 = col_v2.selectbox("📦 1. 選擇廠商", options=all_v2, key="hist_t_vendor")
                        v_filtered = po_work[po_work["vendor_name_disp"] == sel_v2].copy()

                        all_i2 = sorted(
                            [x for x in v_filtered["item_name_disp"].dropna().unique().tolist() if str(x).strip()]
                        )

                        if not all_i2:
                            st.info("💡 此廠商目前無品項資料。")
                        else:
                            sel_i2 = col_i2.selectbox("🏷️ 2. 選擇品項", options=all_i2, key="hist_t_item")
                            p_df = v_filtered[v_filtered["item_name_disp"] == sel_i2].copy()

                            trend = (
                                p_df.groupby("order_date_dt", as_index=False)["order_qty_num"]
                                .sum()
                                .sort_values("order_date_dt")
                            )
                            trend["日期標記"] = pd.to_datetime(trend["order_date_dt"]).dt.strftime("%Y-%m-%d")

                            if not trend.empty:
                                fig = px.line(
                                    trend,
                                    x="日期標記",
                                    y="order_qty_num",
                                    markers=True,
                                    title=f"📈 【{sel_i2}】叫貨趨勢",
                                )
                                fig.update_layout(
                                    xaxis_type="category",
                                    hovermode="x unified",
                                    xaxis_title="日期",
                                    yaxis_title="數量",
                                    dragmode=False,
                                )
                                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    if st.button("⬅️ 返回", use_container_width=True, key="back_hist_final"):
        st.session_state.step = "select_vendor"
        st.rerun()

# ============================================================
# [E5] export - 今日進貨明細輸出
# ============================================================
def page_export():
    st.title("📋 今日進貨明細")

    po_df = _build_purchase_detail_df()

    week_map = {0: "一", 1: "二", 2: "三", 3: "四", 4: "五", 5: "六", 6: "日"}
    delivery_date = st.session_state.record_date + timedelta(days=1)
    header_date = f"{delivery_date.month}/{delivery_date.day}({week_map[delivery_date.weekday()]})"

    if po_df.empty:
        st.info("💡 尚無叫貨資料")
        if st.button("⬅️ 返回選單", use_container_width=True, key="back_to_vendor_export_empty"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    recs = po_df[
        (po_df["store_id"].astype(str).str.strip() == str(st.session_state.store_id).strip())
        & (po_df["order_date_dt"] == st.session_state.record_date)
        & (po_df["order_qty_num"] > 0)
    ].copy()

    if recs.empty:
        st.info("💡 今日尚無叫貨紀錄")
        if st.button("⬅️ 返回選單", use_container_width=True, key="back_to_vendor_export_nodata"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    store_name = st.session_state.store_name
    output = f"{store_name}\n{header_date}\n"

    vendor_order = (
        recs.groupby(["vendor_id", "vendor_name_disp"], as_index=False)["amount_num"]
        .sum()
        .sort_values("vendor_name_disp")
    )

    for _, v in vendor_order.iterrows():
        vendor_id = _norm(v.get("vendor_id", ""))
        vendor_name = _norm(v.get("vendor_name_disp", ""))

        output += f"\n{vendor_name}\n{store_name}\n"

        vendor_rows = recs[recs["vendor_id"].astype(str).str.strip() == vendor_id].copy()
        vendor_rows = vendor_rows.sort_values("item_name_disp")

        for _, r in vendor_rows.iterrows():
            qty = float(r["order_qty_num"])
            qty_display = int(qty) if qty.is_integer() else qty
            output += f"{r['item_name_disp']} {qty_display} {r['order_unit_disp']}\n"

        output += f"禮拜{week_map[delivery_date.weekday()]}到，謝謝\n"

    st.text_area("📱 LINE 訊息內容預覽", value=output, height=350)

    if st.button("🚀 直接發送明細至 LINE", type="primary", use_container_width=True):
        if send_line_message(output):
            st.success(f"✅ 已成功推送到 {store_name} 群組！")
        else:
            st.error("❌ 發送失敗，請檢查 LINE 設定。")

    if st.button("⬅️ 返回選單", use_container_width=True, key="back_to_vendor_export"):
        st.session_state.step = "select_vendor"
        st.rerun()


# ============================================================
# [E6] analysis - 進銷存分析中心
# ============================================================
def page_analysis():
    st.title("📊 進銷存分析")

    po_df = _build_purchase_detail_df()
    stock_df = _build_stock_detail_df()
    prices_df = read_table("prices")

    c_date1, c_date2 = st.columns(2)
    start = c_date1.date_input("起始日期", value=date.today() - timedelta(days=14), key="ana_start")
    end = c_date2.date_input("結束日期", value=date.today(), key="ana_end")

    if (po_df.empty or "store_id" not in po_df.columns) and (stock_df.empty or "store_id" not in stock_df.columns):
        st.error("❌ 無資料")
        if st.button("⬅️ 返回選單", use_container_width=True, key="back_from_analysis_empty"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    po_store = pd.DataFrame()
    stock_store = pd.DataFrame()

    if not po_df.empty and "store_id" in po_df.columns and "order_date_dt" in po_df.columns:
        po_store = po_df[
            po_df["store_id"].astype(str).str.strip() == str(st.session_state.store_id).strip()
        ].copy()
        po_store = po_store[
            po_store["order_date_dt"].notna()
            & (po_store["order_date_dt"] >= start)
            & (po_store["order_date_dt"] <= end)
        ].copy()

    if not stock_df.empty and "store_id" in stock_df.columns and "stocktake_date_dt" in stock_df.columns:
        stock_store = stock_df[
            stock_df["store_id"].astype(str).str.strip() == str(st.session_state.store_id).strip()
        ].copy()
        stock_store = stock_store[
            stock_store["stocktake_date_dt"].notna()
            & (stock_store["stocktake_date_dt"] >= start)
            & (stock_store["stocktake_date_dt"] <= end)
        ].copy()

    if po_store.empty and stock_store.empty:
        st.warning(f"⚠️ 在 {start} 到 {end} 之間查無紀錄。")
        if st.button("⬅️ 返回選單", use_container_width=True, key="back_from_analysis_no_data"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    st.markdown("---")

    col_v, col_i = st.columns(2)

    all_vendors = sorted(
        list(
            set([x for x in po_store.get("vendor_name_disp", pd.Series(dtype=str)).dropna().tolist() if str(x).strip()])
            | set([x for x in stock_store.get("vendor_name_disp", pd.Series(dtype=str)).dropna().tolist() if str(x).strip()])
        )
    )
    all_v = ["全部廠商"] + all_vendors
    selected_v = col_v.selectbox("📦 1. 選擇廠商", options=all_v, index=0, key="ana_v_box")

    po_filt = po_store.copy()
    stock_filt = stock_store.copy()

    if selected_v != "全部廠商":
        if not po_filt.empty:
            po_filt = po_filt[po_filt["vendor_name_disp"] == selected_v].copy()
        if not stock_filt.empty:
            stock_filt = stock_filt[stock_filt["vendor_name_disp"] == selected_v].copy()

    all_items = sorted(
        list(
            set([x for x in po_filt.get("item_name_disp", pd.Series(dtype=str)).dropna().tolist() if str(x).strip()])
            | set([x for x in stock_filt.get("item_name_disp", pd.Series(dtype=str)).dropna().tolist() if str(x).strip()])
        )
    )
    all_i = ["全部品項"] + all_items
    selected_item = col_i.selectbox("🏷️ 2. 選擇品項", options=all_i, index=0, key="ana_i_box")

    if selected_item != "全部品項":
        if not po_filt.empty:
            po_filt = po_filt[po_filt["item_name_disp"] == selected_item].copy()
        if not stock_filt.empty:
            stock_filt = stock_filt[stock_filt["item_name_disp"] == selected_item].copy()

    total_buy = float(po_filt.get("amount_num", pd.Series(dtype=float)).sum()) if not po_filt.empty else 0.0

    if not stock_filt.empty:
        latest_stock = stock_filt.sort_values("stocktake_date_dt").groupby("item_id", as_index=False).tail(1).copy()
        latest_stock["est_unit_price"] = latest_stock.apply(
            lambda r: _get_latest_price_for_item(prices_df, _norm(r.get("item_id", "")), end),
            axis=1,
        )
        latest_stock["stock_value"] = latest_stock["base_qty_num"].astype(float) * latest_stock["est_unit_price"].astype(float)
        total_stock_value = float(latest_stock["stock_value"].sum())
    else:
        total_stock_value = 0.0

    st.markdown(
        f"""
        <div style='display: flex; gap: 10px; margin-bottom: 20px;'>
            <div style='flex: 1; padding: 10px; border-radius: 8px; border-left: 4px solid #4A90E2; background: rgba(74, 144, 226, 0.05);'>
                <div style='font-size: 11px; font-weight: 700; opacity: 0.8;'>💰 採購總額</div>
                <div style='font-size: 18px; font-weight: 800; color: #4A90E2;'>${total_buy:,.1f}</div>
            </div>
            <div style='flex: 1; padding: 10px; border-radius: 8px; border-left: 4px solid #50C878; background: rgba(80, 200, 120, 0.05);'>
                <div style='font-size: 11px; font-weight: 700; opacity: 0.8;'>📦 庫存殘值估計</div>
                <div style='font-size: 18px; font-weight: 800; color: #50C878;'>${total_stock_value:,.1f}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    t_detail, t_trend = st.tabs(["📋 明細", "📈 趨勢"])

    with t_detail:
        st.write("<b>📋 進銷存匯總明細</b>", unsafe_allow_html=True)

        if po_filt.empty:
            st.info("💡 尚未產生採購資料")
        else:
            summ_df = (
                po_filt.groupby(
                    ["vendor_name_disp", "item_name_disp", "order_unit_disp", "unit_price_num"],
                    as_index=False,
                )
                .agg(
                    叫貨數量=("order_qty_num", "sum"),
                    採購金額=("amount_num", "sum"),
                )
                .rename(
                    columns={
                        "vendor_name_disp": "廠商",
                        "item_name_disp": "品項名稱",
                        "order_unit_disp": "單位",
                        "unit_price_num": "單價",
                    }
                )
            )

            st.dataframe(
                summ_df.sort_values("採購金額", ascending=False),
                use_container_width=True,
                hide_index=True,
            )

    with t_trend:
        if not HAS_PLOTLY:
            st.info("💡 Plotly 未安裝，無法顯示趨勢圖。")
        else:
            if not po_filt.empty:
                trend_daily = (
                    po_filt.groupby("order_date_dt", as_index=False)["amount_num"]
                    .sum()
                    .sort_values("order_date_dt")
                )
                trend_daily["日期標記"] = pd.to_datetime(trend_daily["order_date_dt"]).dt.strftime("%Y-%m-%d")

                if not trend_daily.empty:
                    fig1 = px.line(
                        trend_daily,
                        x="日期標記",
                        y="amount_num",
                        markers=True,
                        title="📈 採購金額趨勢",
                    )
                    fig1.update_layout(
                        xaxis_type="category",
                        hovermode="x unified",
                        xaxis_title="日期",
                        yaxis_title="金額",
                        dragmode=False,
                    )
                    st.plotly_chart(fig1, use_container_width=True, config=PLOTLY_CONFIG)

                rank_df = (
                    po_filt.groupby("item_name_disp", as_index=False)["amount_num"]
                    .sum()
                    .sort_values("amount_num", ascending=False)
                    .head(20)
                )

                if not rank_df.empty:
                    fig2 = px.bar(
                        rank_df,
                        x="item_name_disp",
                        y="amount_num",
                        title="📊 品項採購金額排行 (Top 20)",
                    )
                    fig2.update_layout(
                        xaxis_title="品項名稱",
                        yaxis_title="金額",
                        dragmode=False,
                    )
                    st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)
            else:
                st.info("💡 此條件下尚無採購趨勢資料。")

    if st.button("⬅️ 返回選單", use_container_width=True, key="back_from_analysis"):
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
    elif step == "view_history":
        page_view_history()
    elif step == "export":
        page_export()
    elif step == "analysis":
        page_analysis()


# ============================================================
# [G1] Main
# ============================================================
def main():
    apply_global_style()
    init_session()
    router()


if __name__ == "__main__":
    main()
