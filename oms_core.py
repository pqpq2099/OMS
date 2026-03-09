from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Optional

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

from oms_engine import convert_to_base, convert_unit, get_base_unit


# Plotly config (供 pages_reports.py 使用)
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

DEFAULT_SHEET_ID = "1L1ogNjLWjjH8usMWC2JQowMMZkfD4zkuE-4UcgiTqXQ"
LOCAL_SERVICE_ACCOUNT = Path("service_account.json")


# ============================================================
# Global UI Style
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


def apply_table_report_style():
    st.markdown(
        """
        <style>
        [data-testid="stDataFrameToolbar"] {
            display: none !important;
        }

        [data-testid="stDataFrame"] [role="columnheader"] {
            pointer-events: none !important;
        }

        [data-testid="stDataFrame"] [role="gridcell"] {
            pointer-events: none !important;
        }

        [data-testid="stDataFrame"] div[role="grid"] {
            pointer-events: auto !important;
        }

        [data-testid="stDataFrame"] [role="columnheader"],
        [data-testid="stDataFrame"] [role="gridcell"] {
            font-size: 11px !important;
            line-height: 1.1 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_report_dataframe(df: pd.DataFrame, column_config: dict | None = None):
    apply_table_report_style()
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config=column_config or {},
    )


# ============================================================
# Basic Helpers
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


def _clean_option_list(values: list) -> list[str]:
    out = []
    for x in values:
        text = str(x).strip()
        if not text:
            continue
        if text.lower() in {"nan", "none", "nat"}:
            continue
        out.append(text)
    return sorted(list(dict.fromkeys(out)))


def _parse_vendor_id_from_note(note: str) -> str:
    text = _norm(note)
    if "vendor=" not in text:
        return ""
    try:
        return text.split("vendor=", 1)[1].strip()
    except Exception:
        return ""


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


def _sort_items_for_operation(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    work = df.copy()
    work["_display_name"] = work.apply(_item_display_name, axis=1)

    if "display_order" in work.columns:
        work["_display_order_num"] = pd.to_numeric(work["display_order"], errors="coerce").fillna(999999)
        work = work.sort_values(["_display_order_num", "_display_name"], ascending=[True, True])
    else:
        work = work.sort_values(["_display_name"], ascending=[True])

    return work


def _status_hint(total_stock: float, daily_avg: float, suggest_qty: float) -> str:
    total_stock = _safe_float(total_stock)
    daily_avg = _safe_float(daily_avg)
    suggest_qty = _safe_float(suggest_qty)

    if daily_avg > 0 and total_stock < daily_avg:
        return "🔴"
    if suggest_qty > 0 and total_stock < suggest_qty:
        return "🟡"
    return ""


# ============================================================
# Google Sheets Client
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


def _get_secret_sheet_id() -> str:
    try:
        if hasattr(st.secrets, "get"):
            return st.secrets.get("sheet_id", DEFAULT_SHEET_ID)
    except Exception:
        pass
    return DEFAULT_SHEET_ID


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
# Sheet Read / Write
# ============================================================
@st.cache_data(show_spinner=False, ttl=120)
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


def append_rows_by_header(sheet_name: str, header: list[str], rows: list[dict]):
    if not rows:
        return

    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet(sheet_name)
    values = [[row.get(col, "") for col in header] for row in rows]
    ws.append_rows(values, value_input_option="USER_ENTERED")


def bust_cache():
    read_table.clear()


# ============================================================
# LINE Push
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
# ID Sequence
# ============================================================
def _make_id(prefix: str, width: int, n: int) -> str:
    return f"{prefix}{str(n).zfill(int(width))}"


def allocate_ids(request_counts: dict[str, int], env: str = "prod") -> dict[str, list[str]]:
    request_counts = {k: int(v) for k, v in request_counts.items() if int(v) > 0}
    result = {k: [] for k in request_counts.keys()}

    if not request_counts:
        return result

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

    required = ["key", "env", "prefix", "width", "next_value"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"id_sequences 缺少欄位：{col}")

    now = _now_ts()

    for key, cnt in request_counts.items():
        hit = df[
            (df["key"].astype(str).str.strip() == str(key).strip())
            & (df["env"].astype(str).str.strip() == str(env).strip())
        ]

        if hit.empty:
            raise ValueError(f"id_sequences 找不到 key={key}, env={env}")

        idx = hit.index[0]
        prefix = _norm(df.at[idx, "prefix"])
        width = int(_safe_float(df.at[idx, "width"], 0))
        next_value = int(_safe_float(df.at[idx, "next_value"], 0))

        if not prefix or width <= 0 or next_value <= 0:
            raise ValueError(f"id_sequences 設定錯誤：key={key}")

        ids = [_make_id(prefix, width, next_value + i) for i in range(cnt)]
        result[key] = ids

        df.at[idx, "next_value"] = str(next_value + cnt)
        if "updated_at" in df.columns:
            df.at[idx, "updated_at"] = now

    out_values = [header] + df[header].fillna("").astype(str).values.tolist()
    ws.update(out_values)

    bust_cache()
    return result


# ============================================================
# Data Helpers
# ============================================================
def get_base_unit_cost(item_id, target_date, items_df, prices_df, conversions_df):
    if items_df.empty or prices_df.empty:
        return None

    item_row = items_df[items_df["item_id"].astype(str).str.strip() == str(item_id).strip()]
    if item_row.empty:
        return None

    base_unit = str(item_row.iloc[0].get("base_unit", "")).strip()
    if not base_unit:
        return None

    price_rows = prices_df.copy()
    price_rows = price_rows[
        price_rows["item_id"].astype(str).str.strip() == str(item_id).strip()
    ]

    if "is_active" in price_rows.columns:
        price_rows = price_rows[
            price_rows["is_active"].apply(
                lambda x: str(x).strip() in ["1", "True", "true", "YES", "yes", "是"]
            )
        ]

    if price_rows.empty:
        return None

    price_rows["__eff"] = price_rows["effective_date"].apply(_parse_date)
    price_rows["__end"] = price_rows["end_date"].apply(_parse_date)

    price_rows = price_rows[
        (price_rows["__eff"].isna() | (price_rows["__eff"] <= target_date))
        & (price_rows["__end"].isna() | (price_rows["__end"] >= target_date))
    ]

    if price_rows.empty:
        return None

    price_rows = price_rows.sort_values("__eff", ascending=True)
    price_row = price_rows.iloc[-1]

    unit_price = _safe_float(price_row.get("unit_price", 0))
    price_unit = str(price_row.get("price_unit", "")).strip()

    if unit_price == 0:
        return None

    if price_unit == base_unit or price_unit == "":
        return unit_price

    conv = conversions_df[
        (conversions_df["item_id"].astype(str).str.strip() == str(item_id).strip())
        & (conversions_df["from_unit"].astype(str).str.strip() == price_unit)
        & (conversions_df["to_unit"].astype(str).str.strip() == base_unit)
    ]

    if conv.empty:
        return None

    ratio = _safe_float(conv.iloc[0].get("ratio", 0))
    if ratio == 0:
        return None

    return round(unit_price / ratio, 4)


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
        for c in ["base_unit", "default_vendor_id", "default_stock_unit", "display_order"]:
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

    merged["vendor_name_disp"] = merged["vendor_name_disp"].apply(
        lambda x: "" if _norm(x).lower() in {"", "nan", "none", "nat", "-"} else _norm(x)
    )
    merged["item_name_disp"] = merged["item_name_disp"].apply(
        lambda x: "未指定" if _norm(x).lower() in {"", "nan", "none", "nat"} else _norm(x)
    )
    merged["store_name_disp"] = merged["store_name_disp"].apply(
        lambda x: "未指定" if _norm(x).lower() in {"", "nan", "none", "nat"} else _norm(x)
    )

    merged["order_date_dt"] = merged["order_date"].apply(_parse_date)

    merged["order_qty_num"] = pd.to_numeric(
        _coalesce_columns(merged, ["order_qty", "qty"], default=0),
        errors="coerce"
    ).fillna(0)

    merged["order_base_qty_num"] = pd.to_numeric(
        _coalesce_columns(merged, ["base_qty"], default=0),
        errors="coerce"
    ).fillna(0)

    merged["order_base_unit_disp"] = _coalesce_columns(
        merged, ["base_unit"], default=""
    ).astype(str).str.strip()

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

    merged["order_unit_disp"] = _coalesce_columns(
        merged, ["order_unit", "unit_id"], default=""
    ).astype(str).str.strip()

    if "display_order" in merged.columns:
        merged["display_order_num"] = pd.to_numeric(merged["display_order"], errors="coerce").fillna(999999)
    else:
        merged["display_order_num"] = 999999

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
        for c in ["base_unit", "default_vendor_id", "default_stock_unit", "display_order"]:
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

    merged["vendor_name_disp"] = merged["vendor_name_disp"].apply(
        lambda x: "-" if _norm(x).lower() in {"", "nan", "none", "nat"} else _norm(x)
    )
    merged["item_name_disp"] = merged["item_name_disp"].apply(
        lambda x: "未指定" if _norm(x).lower() in {"", "nan", "none", "nat"} else _norm(x)
    )
    merged["store_name_disp"] = merged["store_name_disp"].apply(
        lambda x: "未指定" if _norm(x).lower() in {"", "nan", "none", "nat"} else _norm(x)
    )

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

    if "display_order" in merged.columns:
        merged["display_order_num"] = pd.to_numeric(merged["display_order"], errors="coerce").fillna(999999)
    else:
        merged["display_order_num"] = 999999

    return merged.copy()


def _sum_purchase_qty_in_display_unit(
    item_po: pd.DataFrame,
    item_id: str,
    display_unit: str,
    conversions_df: pd.DataFrame,
    curr_date: date,
) -> float:
    total = 0.0
    if item_po.empty:
        return 0.0

    for _, po_row in item_po.iterrows():
        base_qty = _safe_float(po_row.get("order_base_qty_num", 0))
        base_unit = _norm(po_row.get("order_base_unit_disp", ""))

        if base_qty == 0:
            continue

        try:
            if base_unit and display_unit and base_unit != display_unit:
                qty_in_display = convert_unit(
                    item_id=item_id,
                    qty=base_qty,
                    from_unit=base_unit,
                    to_unit=display_unit,
                    conversions_df=conversions_df,
                    as_of_date=curr_date,
                )
            else:
                qty_in_display = base_qty
            total += float(qty_in_display)
        except Exception:
            total += float(base_qty)

    return round(total, 1)


def _build_inventory_history_summary_df(store_id: str, start_date: date, end_date: date) -> pd.DataFrame:
    stock_df = _build_stock_detail_df()
    po_df = _build_purchase_detail_df()
    conversions_df = _get_active_df(read_table("unit_conversions"))

    if stock_df.empty or "store_id" not in stock_df.columns:
        return pd.DataFrame()

    stock_work = stock_df[
        stock_df["store_id"].astype(str).str.strip() == str(store_id).strip()
    ].copy()

    if stock_work.empty or "stocktake_date_dt" not in stock_work.columns:
        return pd.DataFrame()

    stock_work = stock_work[stock_work["stocktake_date_dt"].notna()].copy()

    if "display_order_num" not in stock_work.columns:
        if "display_order" in stock_work.columns:
            stock_work["display_order_num"] = pd.to_numeric(stock_work["display_order"], errors="coerce").fillna(999999)
        else:
            stock_work["display_order_num"] = 999999

    target_stock = stock_work[
        (stock_work["stocktake_date_dt"] >= start_date)
        & (stock_work["stocktake_date_dt"] <= end_date)
    ].copy()

    if target_stock.empty:
        return pd.DataFrame()

    po_work = pd.DataFrame()
    if not po_df.empty and "store_id" in po_df.columns and "order_date_dt" in po_df.columns:
        po_work = po_df[
            po_df["store_id"].astype(str).str.strip() == str(store_id).strip()
        ].copy()
        po_work = po_work[po_work["order_date_dt"].notna()].copy()

    result_rows = []

    target_stock = target_stock.sort_values(
        ["stocktake_date_dt", "display_order_num", "item_name_disp"],
        ascending=[True, True, True]
    ).copy()

    for _, curr_row in target_stock.iterrows():
        item_id = _norm(curr_row.get("item_id", ""))
        curr_date = curr_row.get("stocktake_date_dt")
        item_name = _norm(curr_row.get("item_name_disp", "")) or "未指定"
        display_order_num = _safe_float(curr_row.get("display_order_num", 999999))
        unit = _norm(curr_row.get("display_stock_unit", "")) or _norm(curr_row.get("base_unit", ""))

        item_stock_all = stock_work[
            stock_work["item_id"].astype(str).str.strip() == item_id
        ].copy()

        prev_stock = item_stock_all[item_stock_all["stocktake_date_dt"] < curr_date].sort_values("stocktake_date_dt")

        if prev_stock.empty:
            prev_qty = 0.0
            prev_date = None
        else:
            prev_qty = _safe_float(prev_stock.iloc[-1].get("display_stock_qty", 0))
            prev_date = prev_stock.iloc[-1].get("stocktake_date_dt")

                curr_qty = _safe_float(curr_row.get("display_stock_qty", 0))

        
        # 第一次紀錄：不補前帳、不補前面進貨
        if prev_date is None:
            order_sum = 0.0
            total_stock = 0.0
            usage = 0.0
            days = 0
            daily_avg = 0.0
        else:
            order_sum = 0.0
            if not po_work.empty:
                item_po = po_work[
                    po_work["item_id"].astype(str).str.strip() == item_id
                ].copy()

                item_po = item_po[
                    (item_po["order_date_dt"] > prev_date)
                    & (item_po["order_date_dt"] <= curr_date)
                ]

                order_sum = _sum_purchase_qty_in_display_unit(
                    item_po=item_po,
                    item_id=item_id,
                    display_unit=unit,
                    conversions_df=conversions_df,
                    curr_date=curr_date,
                )

            total_stock = round(prev_qty + order_sum, 1)
            usage = round(total_stock - curr_qty, 1)
            days = max((curr_date - prev_date).days, 1)
            daily_avg = round(usage / days, 1)
                
        result_rows.append(
            {
                "日期": curr_date,
                "品項": item_name,
                "上次庫存": round(prev_qty, 1),
                "期間進貨": round(order_sum, 1),
                "庫存合計": total_stock,
                "這次庫存": round(curr_qty, 1),
                "期間消耗": usage,
                "日平均": daily_avg,
                "天數": days,
                "item_id": item_id,
                "display_order_num": display_order_num,
            }
        )

    out = pd.DataFrame(result_rows)
    if out.empty:
        return out

    out["日期_dt"] = pd.to_datetime(out["日期"], errors="coerce")
    out["日期顯示"] = out["日期_dt"].dt.strftime("%m-%d")
    out = out.sort_values(["日期_dt", "display_order_num", "品項"], ascending=[False, True, True]).reset_index(drop=True)
    return out


def _build_latest_item_metrics_df(store_id: str, as_of_date: date) -> pd.DataFrame:
    hist_df = _build_inventory_history_summary_df(
        store_id=store_id,
        start_date=date(2000, 1, 1),
        end_date=as_of_date,
    )

    if hist_df.empty:
        return pd.DataFrame()

    work = hist_df.copy()
    work = work.sort_values(["日期_dt", "display_order_num", "品項"], ascending=[False, True, True])
    latest = work.groupby("item_id", as_index=False).head(1).copy()
    latest = latest.sort_values(["display_order_num", "品項"], ascending=[True, True]).reset_index(drop=True)
    return latest


def _build_purchase_summary_df(store_id: str, start_date: date, end_date: date) -> pd.DataFrame:
    po_df = _build_purchase_detail_df()
    if po_df.empty or "store_id" not in po_df.columns or "order_date_dt" not in po_df.columns:
        return pd.DataFrame()

    po_work = po_df[
        po_df["store_id"].astype(str).str.strip() == str(store_id).strip()
    ].copy()

    po_work = po_work[
        po_work["order_date_dt"].notna()
        & (po_work["order_date_dt"] >= start_date)
        & (po_work["order_date_dt"] <= end_date)
    ].copy()

    if po_work.empty:
        return pd.DataFrame()

    po_work["廠商"] = po_work["vendor_name_disp"].apply(
        lambda x: "" if _norm(x).lower() in {"", "nan", "none", "nat", "-"} else _norm(x)
    )
    po_work["品項名稱"] = po_work["item_name_disp"].apply(
        lambda x: _norm(x) or "未指定"
    )
    po_work["單位"] = po_work["order_unit_disp"].apply(lambda x: _norm(x))
    po_work["單價"] = po_work["unit_price_num"].astype(float)
    po_work["叫貨數量"] = po_work["order_qty_num"].astype(float)
    po_work["採購金額"] = po_work["amount_num"].astype(float)

    out = (
        po_work.groupby(["廠商", "品項名稱", "單位", "單價"], as_index=False)
        .agg(
            叫貨數量=("叫貨數量", "sum"),
            採購金額=("採購金額", "sum"),
        )
        .sort_values(["廠商", "品項名稱"], ascending=[True, True])
        .reset_index(drop=True)
    )
    return out


