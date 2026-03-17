# ============================================================
# ORIVIA OMS
# 檔案：oms_core.py
# 說明：ORIVIA OMS 核心整合模組
# 功能：整合共用工具、資料讀寫包裝、舊版相容函式與跨頁面共用邏輯。
# 注意：此檔為目前專案的重要相容層，不建議隨意拆解。
# ============================================================

"""
OMS 核心共用模組。

這個檔案放的是很多頁面都會用到的共用函式，包含：
1. 讀取 Google Sheets
2. 共用格式整理
3. 報表計算輔助
4. UI 共用樣式

如果某個功能很多頁都會用到，通常就會放在這裡。
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Optional
import copy

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

from utils.utils_units import convert_to_base, convert_unit, get_base_unit


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
BASE_DIR = Path(__file__).resolve().parent
LOCAL_SERVICE_ACCOUNT = BASE_DIR / "service_account.json"

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
            padding: 4px 2px !important;
        }

        /* 隱藏 number_input +/- */
        div[data-testid="stNumberInputStepUp"],
        div[data-testid="stNumberInputStepDown"] {
            display: none !important;
        }

        input[type=number] {
            -moz-appearance: textfield !important;
            -webkit-appearance: none !important;
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


def render_report_dataframe(
    df: pd.DataFrame,
    column_config: dict | None = None,
    height: int | None = None,
):
    apply_table_report_style()

    dataframe_kwargs = {
        "use_container_width": True,
        "hide_index": True,
        "column_config": column_config or {},
    }

    # 某些 Streamlit 版本不接受 height=None
    if height is not None:
        dataframe_kwargs["height"] = height

    st.dataframe(
        df,
        **dataframe_kwargs,
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
    """
    作業頁品項排序規則：
    1. 若有 display_order，優先依 display_order 排。
    2. 若沒有 display_order，改依 item_id 的流水序號排，避免被品項名稱影響順序。
    3. 若 item_id 無法拆出數字，最後才用顯示名稱當備援排序。
    """
    if df is None or df.empty:
        return df

    work = df.copy()
    work["_display_name"] = work.apply(_item_display_name, axis=1)

    if "display_order" in work.columns:
        work["_display_order_num"] = pd.to_numeric(work["display_order"], errors="coerce").fillna(999999)
        work = work.sort_values(["_display_order_num", "_display_name"], ascending=[True, True])
        return work

    work["_item_id_sort"] = work.get("item_id", "").astype(str).str.extract(r"(\d+)$", expand=False)
    work["_item_id_sort"] = pd.to_numeric(work["_item_id_sort"], errors="coerce").fillna(999999)
    work["_item_id_raw"] = work.get("item_id", "").astype(str)

    work = work.sort_values(["_item_id_sort", "_item_id_raw", "_display_name"], ascending=[True, True, True])
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
# [C1] Google Sheets Client
# 這一區放：Google Sheets 連線 / Spreadsheet 取得
# ============================================================
def _get_secret_sheet_id() -> str:
    try:
        if hasattr(st.secrets, "get"):
            return st.secrets.get("SHEET_ID") or st.secrets.get("sheet_id") or DEFAULT_SHEET_ID
    except Exception:
        pass
    return DEFAULT_SHEET_ID


@st.cache_resource(show_spinner=False)
def get_gspread_client():
    """
    Google Sheets 驗證入口
    優先順序：
    1. st.secrets["gcp_service_account"]
    2. st.secrets["gcp"]
    3. 本機 service_account.json
    """
    try:
        info = None

        if "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
        elif "gcp" in st.secrets:
            info = dict(st.secrets["gcp"])
        elif LOCAL_SERVICE_ACCOUNT.exists():
            import json
            info = json.loads(LOCAL_SERVICE_ACCOUNT.read_text(encoding="utf-8"))

        if not info:
            st.error("找不到 Google Service Account 設定")
            return None

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        return gspread.authorize(creds)

    except Exception as e:
        st.error(f"Google Sheets 驗證失敗：{e}")
        return None


@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    """
    取得目前主資料庫 Spreadsheet
    """
    client = get_gspread_client()
    if not client:
        return None

    try:
        return client.open_by_key(_get_secret_sheet_id())
    except Exception as e:
        st.error(f"開啟 Sheet 失敗：{e}")
        return None


# ============================================================
# [C2] Sheet Read / Write
# 這一區放：讀表、抓表頭、寫入資料、清快取
# ============================================================
def _get_runtime_table_cache() -> dict:
    """
    取得本次使用者 session 的表格快取。
    目的：
    1. 同一次操作流程中，避免同一張表被重複打到 Google Sheets。
    2. 當 Google API 暫時 429 時，優先回傳最近一次成功資料，降低整頁爆掉機率。
    """
    return st.session_state.setdefault("_runtime_table_cache", {})


@st.cache_data(show_spinner=False, ttl=300)
def _read_table_remote(sheet_name: str) -> pd.DataFrame:
    sh = get_spreadsheet()
    if sh is None:
        return pd.DataFrame()

    ws = sh.worksheet(sheet_name)
    values = ws.get_all_values()

    # 連表頭都沒有
    if not values:
        return pd.DataFrame()

    header = [_norm(c) for c in values[0]]
    rows = values[1:]

    # 只有表頭，沒有資料列
    if not rows:
        return pd.DataFrame(columns=header)

    normalized_rows = []
    for row in rows:
        row = list(row)

        # 補齊不足欄位
        if len(row) < len(header):
            row = row + [""] * (len(header) - len(row))
        else:
            row = row[:len(header)]

        normalized_rows.append(row)

    df = pd.DataFrame(normalized_rows, columns=header)

    # 移除整列都空白的資料，但保留表頭
    if not df.empty:
        df = df[
            df.apply(lambda r: any(_norm(v) != "" for v in r), axis=1)
        ].reset_index(drop=True)

    return df


@st.cache_data(show_spinner=False, ttl=300)
def _get_header_remote(sheet_name: str) -> list[str]:
    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet(sheet_name)
    header = ws.row_values(1)
    if not header:
        raise ValueError(f"{sheet_name} 沒有 header")
    return [_norm(h) for h in header]


def read_table(sheet_name: str, force_refresh: bool = False) -> pd.DataFrame:
    """
    讀取 Google Sheet 表格。
    這裡採兩層快取：
    1. Streamlit cache_data：跨 rerun 短時間共用
    2. session_state runtime cache：同一位使用者當前操作流程直接重用

    另外當 Google API 暫時 429 / timeout 時：
    - 若 session 內已有最近一次成功資料，優先回傳舊資料
    - 目的不是永久吃舊資料，而是避免單次畫面整頁炸掉
    """
    cache = _get_runtime_table_cache()
    cache_key = _norm(sheet_name)

    if force_refresh:
        cache.pop(cache_key, None)
        _read_table_remote.clear()

    if cache_key in cache:
        return cache[cache_key].copy()

    try:
        df = _read_table_remote(sheet_name)
        cache[cache_key] = df.copy()
        return df.copy()
    except Exception as e:
        old_df = cache.get(cache_key)
        if old_df is not None:
            st.warning(f"{sheet_name} 讀取失敗，已改用暫存資料：{e}")
            return old_df.copy()

        st.warning(f"{sheet_name} 讀取失敗：{e}")
        return pd.DataFrame()


def get_header(sheet_name: str, force_refresh: bool = False) -> list[str]:
    cache = st.session_state.setdefault("_runtime_header_cache", {})
    cache_key = _norm(sheet_name)

    if force_refresh:
        cache.pop(cache_key, None)
        _get_header_remote.clear()

    if cache_key in cache:
        return list(cache[cache_key])

    try:
        header = _get_header_remote(sheet_name)
        cache[cache_key] = list(header)
        return list(header)
    except Exception as e:
        old_header = cache.get(cache_key)
        if old_header is not None:
            st.warning(f"{sheet_name} header 讀取失敗，已改用暫存資料：{e}")
            return list(old_header)
        raise


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
    """
    清除資料快取。
    只要有寫入 / 更新 / 刪除後，都應呼叫這裡，避免畫面繼續看到舊資料。
    """
    _read_table_remote.clear()
    _get_header_remote.clear()
    st.session_state.pop("_runtime_table_cache", None)
    st.session_state.pop("_runtime_header_cache", None)


# ============================================================
# [D1] LINE Push
# 這一區放：LINE 推播
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
# [D2] ID Sequence
# 這一區放：自動編號 / ID 產生
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
# [E1] Data Helpers
# 這一區放：價格、最後叫貨、最後庫存等資料整理工具
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
    as_of_date: date | None = None,
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
    if as_of_date is not None:
        merged = merged[merged["__date"].notna() & (merged["__date"] <= as_of_date)].copy()
        if merged.empty:
            return 0.0
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
# [F1] Purchase / Stock Detail Builders
# 這一區放：進貨明細、庫存明細
# ============================================================
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
    if "delivery_date" in po_keep.columns:
        rename_map["delivery_date"] = "po_delivery_date"
    if "expected_date" in po_keep.columns:
        rename_map["expected_date"] = "po_expected_date"
    if "status" in po_keep.columns:
        rename_map["status"] = "po_status"

    po_keep = po_keep.rename(columns=rename_map)

    keep_cols = ["po_id"]
    for c in ["po_store_id", "po_vendor_id", "po_order_date", "po_delivery_date", "po_expected_date", "po_status"]:
        if c in po_keep.columns:
            keep_cols.append(c)

    merged = pol.merge(po_keep[keep_cols], on="po_id", how="left")

    merged["store_id"] = _coalesce_columns(merged, ["po_store_id", "store_id"], default="")
    merged["vendor_id"] = _coalesce_columns(merged, ["po_vendor_id", "vendor_id"], default="")
    merged["order_date"] = _coalesce_columns(merged, ["po_order_date", "order_date"], default="")
    merged["delivery_date"] = _coalesce_columns(merged, ["delivery_date", "po_delivery_date", "po_expected_date"], default="")
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
    merged["delivery_date_dt"] = merged["delivery_date"].apply(_parse_date)

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
    if "created_at" in st_keep.columns:
        rename_map["created_at"] = "st_created_at"
    if "updated_at" in st_keep.columns:
        rename_map["updated_at"] = "st_updated_at"
    st_keep = st_keep.rename(columns=rename_map)

    keep_cols = ["stocktake_id"]
    for c in ["st_store_id", "st_stocktake_date", "st_note", "st_created_at", "st_updated_at"]:
        if c in st_keep.columns:
            keep_cols.append(c)
    merged = stl.merge(st_keep[keep_cols], on="stocktake_id", how="left")

    merged["store_id"] = _coalesce_columns(merged, ["st_store_id", "store_id"], default="")
    merged["stocktake_date"] = _coalesce_columns(merged, ["st_stocktake_date", "stocktake_date"], default="")
    merged["note_for_parse"] = _coalesce_columns(merged, ["st_note", "note"], default="")
    merged["vendor_id"] = _coalesce_columns(merged, ["vendor_id"], default="")
    merged["stocktake_created_at"] = _coalesce_columns(merged, ["st_created_at"], default="")
    merged["stocktake_updated_at"] = _coalesce_columns(merged, ["st_updated_at"], default="")
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


# ============================================================
# [F2] Report Builders
# 這一區放：進銷存摘要、最新品項指標、進貨摘要
# ============================================================
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
    # ========================================================
    # 同日同廠商同品項，只保留最後一張盤點單
    # 避免同一天重複建立 ST_000002 / ST_000003 時，報表重複顯示
    # ========================================================
    if "stocktake_updated_at" not in target_stock.columns:
        target_stock["stocktake_updated_at"] = ""
    if "stocktake_created_at" not in target_stock.columns:
        target_stock["stocktake_created_at"] = ""

    target_stock["__sort_updated"] = pd.to_datetime(
        target_stock["stocktake_updated_at"], errors="coerce"
    )
    target_stock["__sort_created"] = pd.to_datetime(
        target_stock["stocktake_created_at"], errors="coerce"
    )

    target_stock = target_stock.sort_values(
        [
            "stocktake_date_dt",
            "vendor_id",
            "item_id",
            "__sort_updated",
            "__sort_created",
            "stocktake_id",
        ],
        ascending=[True, True, True, True, True, True],
    ).copy()

    target_stock = target_stock.drop_duplicates(
        subset=["stocktake_date_dt", "vendor_id", "item_id"],
        keep="last",
    ).copy()

    # 同日＋同廠商＋同品項，只保留最後一張盤點單
    if "stocktake_updated_at" not in target_stock.columns:
        target_stock["stocktake_updated_at"] = ""
    if "stocktake_created_at" not in target_stock.columns:
        target_stock["stocktake_created_at"] = ""
    
    target_stock["__sort_updated"] = pd.to_datetime(
        target_stock["stocktake_updated_at"], errors="coerce"
    )
    target_stock["__sort_created"] = pd.to_datetime(
        target_stock["stocktake_created_at"], errors="coerce"
    )
    
    target_stock = target_stock.sort_values(
        [
            "stocktake_date_dt",
            "vendor_id",
            "item_id",
            "__sort_updated",
            "__sort_created",
            "stocktake_id",
        ],
        ascending=[True, True, True, True, True, True],
    ).copy()
    
    target_stock = target_stock.drop_duplicates(
        subset=["stocktake_date_dt", "vendor_id", "item_id"],
        keep="last",
    ).copy()
    
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

        current_order_qty = 0.0
        if not po_work.empty:
            item_po_same_day = po_work[
                (po_work["item_id"].astype(str).str.strip() == item_id)
                & (po_work["order_date_dt"] == curr_date)
            ].copy()

            current_order_qty = _sum_purchase_qty_in_display_unit(
                item_po=item_po_same_day,
                item_id=item_id,
                display_unit=unit,
                conversions_df=conversions_df,
                curr_date=curr_date,
            )

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
                "這次叫貨": round(current_order_qty, 1),
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
    date_field = "delivery_date_dt" if "delivery_date_dt" in po_df.columns else "order_date_dt"
    if po_df.empty or "store_id" not in po_df.columns or date_field not in po_df.columns:
        return pd.DataFrame()

    po_work = po_df[
        po_df["store_id"].astype(str).str.strip() == str(store_id).strip()
    ].copy()

    po_work = po_work[
        po_work[date_field].notna()
        & (po_work[date_field] >= start_date)
        & (po_work[date_field] <= end_date)
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


# ============================================================
# [UTIL] CSV 匯出工具
# 用途：
# 所有報表統一使用此函式匯出 CSV
# ============================================================
def export_csv_button(df, filename: str, label: str = "📥 匯出 CSV"):
    import streamlit as st

    if df is None or df.empty:
        st.caption("沒有資料可匯出")
        return

    csv_data = df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        label,
        csv_data,
        file_name=filename,
        mime="text/csv",
        use_container_width=False,
    )



