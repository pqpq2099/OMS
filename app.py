import streamlit as st
import pandas as pd
import gspread
from gspread.exceptions import WorksheetNotFound, APIError
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime
import math

# ============================================================
# [A0] Page Config
# ============================================================
st.set_page_config(
    page_title="ORIVIA OMS",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# [A1] Optional Plotly
# ============================================================
try:
    import plotly.express as px
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "scrollZoom": False,
    "doubleClick": False,
    "staticPlot": False,
    "modeBarButtonsToRemove": [
        "zoom2d", "pan2d", "select2d", "lasso2d",
        "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d",
        "hoverClosestCartesian", "hoverCompareCartesian", "toggleSpikelines"
    ],
    "toImageButtonOptions": {
        "format": "png",
        "filename": "orivia_report",
        "scale": 2,
    },
}

# ============================================================
# [A2] Config
# ============================================================
SHEET_ID = "1L1ogNjLWjjH8usMWC2JQowMMZkfD4zkuE-4UcgiTqXQ"
DB_SHEET_ID = SHEET_ID

WS_BRANDS = "brands"
WS_STORES = "stores"
WS_VENDORS = "vendors"
WS_UNITS = "units"
WS_ITEMS = "items"
WS_UNIT_CONVERSIONS = "unit_conversions"
WS_PRICES = "prices"
WS_TRANSACTIONS = "transactions"
WS_STOCKTAKES = "stocktakes"
WS_STOCKTAKE_LINES = "stocktake_lines"
WS_PURCHASE_ORDERS = "purchase_orders"
WS_PO_LINES = "purchase_order_lines"
WS_ROLES = "roles"
WS_USERS = "users"
WS_AUDIT_LOGS = "audit_logs"
WS_SETTINGS = "settings"
WS_ID_SEQUENCES = "id_sequences"

DEFAULT_USER_ID = "U0001"
DEFAULT_ACCOUNT_CODE = "ADMIN_01"
DEFAULT_CURRENCY = "NT$"
APP_VERSION = "OMS Schema v1"

# ============================================================
# [A3] CSS
# ============================================================
CUSTOM_CSS = """
<style>
.block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
}
div[data-testid="stNumberInput"] input {
    text-align: right;
    padding-right: 0.45rem !important;
    padding-left: 0.45rem !important;
}
div[data-testid="stNumberInput"] button {
    display: none !important;
}
div[data-baseweb="select"] > div {
    min-height: 36px !important;
}
div[data-baseweb="select"] span {
    font-size: 0.9rem !important;
}
[data-testid="stCaptionContainer"] {
    margin-top: -0.25rem !important;
}
.orivia-card {
    border: 1px solid rgba(128,128,128,0.25);
    border-radius: 14px;
    padding: 0.7rem 0.8rem 0.55rem 0.8rem;
    margin-bottom: 0.6rem;
    background: rgba(255,255,255,0.02);
}
.orivia-item-name {
    font-weight: 700;
    font-size: 1rem;
    margin-bottom: 0.15rem;
}
.orivia-sub {
    font-size: 0.86rem;
    color: rgba(120,120,120,1);
    margin-bottom: 0.4rem;
}
@media (max-width: 768px) {
  .block-container {
      padding-left: 0.7rem;
      padding-right: 0.7rem;
  }
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ============================================================
# [B0] Utilities
# ============================================================
def _norm(x):
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() == "nan":
        return ""
    return s


def _safe_float(x, default=0.0):
    try:
        if x is None or str(x).strip() == "":
            return default
        return float(x)
    except Exception:
        return default


def _safe_int(x, default=0):
    try:
        return int(float(x))
    except Exception:
        return default


def _fmt_num(x, digits=1):
    try:
        v = float(x)
        if math.isnan(v):
            return f"{0:.{digits}f}"
        return f"{v:.{digits}f}"
    except Exception:
        return f"{0:.{digits}f}"


def _fmt_money(x):
    try:
        return f"{DEFAULT_CURRENCY}{float(x):,.0f}"
    except Exception:
        return f"{DEFAULT_CURRENCY}0"


def _to_date(x):
    try:
        return pd.to_datetime(x).date()
    except Exception:
        return None


def _today_str():
    return date.today().isoformat()


def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df


def item_display_name(row) -> str:
    return _norm(row.get("item_name_zh")) or _norm(row.get("item_name")) or _norm(row.get("item_id"))


def parse_list_field(s: str, fallback: str = "") -> list[str]:
    s = _norm(s)
    if not s:
        return [fallback] if fallback else []
    arr = [x.strip() for x in s.replace("/", ",").replace("、", ",").split(",") if x.strip()]
    if fallback and fallback not in arr:
        arr.insert(0, fallback)
    return arr or ([fallback] if fallback else [])

# ============================================================
# [B1] Google Sheets
# ============================================================
@st.cache_resource(show_spinner=False)
def get_gspread_client():
    if "gcp" not in st.secrets:
        raise RuntimeError("找不到 st.secrets['gcp']，請先設定 Streamlit secrets。")

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp"]), scope)
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def open_spreadsheet(sheet_id: str):
    gc = get_gspread_client()
    return gc.open_by_key(sheet_id)


def get_worksheet(ws_name: str):
    sh = open_spreadsheet(DB_SHEET_ID)
    try:
        return sh.worksheet(ws_name)
    except WorksheetNotFound:
        return sh.add_worksheet(title=ws_name, rows=2000, cols=60)


def read_ws(ws_name: str) -> pd.DataFrame:
    try:
        ws = get_worksheet(ws_name)
        values = ws.get_all_records()
        if not values:
            return pd.DataFrame()
        return pd.DataFrame(values)
    except APIError:
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def write_ws_df(ws_name: str, df: pd.DataFrame):
    ws = get_worksheet(ws_name)
    ws.clear()
    if df.empty:
        ws.update("A1", [[""]])
        return
    rows = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
    ws.update(rows)


def append_rows(ws_name: str, rows: list[list]):
    if not rows:
        return
    ws = get_worksheet(ws_name)
    ws.append_rows(rows, value_input_option="USER_ENTERED")


def ensure_ws_headers(ws_name: str, cols: list[str]):
    ws = get_worksheet(ws_name)
    try:
        header = [str(x).strip() for x in ws.row_values(1)]
    except Exception:
        header = []

    if not header:
        ws.update("A1", [cols])
        return

    merged = header[:]
    for c in cols:
        if c not in merged:
            merged.append(c)
    if merged != header:
        ws.update("A1", [merged])

# ============================================================
# [B2] Schema v1 Bootstrap
# ============================================================
def bootstrap_if_needed():
    required = {
        WS_BRANDS: [
            "brand_id", "brand_name", "brand_name_zh", "is_active", "created_at", "updated_at"
        ],
        WS_STORES: [
            "store_id", "brand_id", "store_name", "store_name_zh", "store_code",
            "is_active", "created_at", "updated_at"
        ],
        WS_VENDORS: [
            "vendor_id", "brand_id", "vendor_name", "vendor_name_zh", "vendor_code",
            "contact_name", "phone", "line_id", "notes", "is_active", "created_at", "updated_at"
        ],
        WS_UNITS: [
            "unit_id", "unit_name", "unit_name_zh", "unit_symbol", "unit_type",
            "is_active", "created_at", "updated_at"
        ],
        WS_ITEMS: [
            "item_id", "brand_id", "default_vendor_id", "item_name", "item_name_zh", "item_type",
            "category", "spec", "base_unit", "default_stock_unit", "default_order_unit",
            "orderable_units", "price", "is_active", "created_at", "updated_at"
        ],
        WS_UNIT_CONVERSIONS: [
            "conversion_id", "item_id", "from_unit", "to_unit", "multiplier",
            "is_active", "created_at", "updated_at"
        ],
        WS_PRICES: [
            "price_id", "item_id", "unit_price", "price_unit", "effective_date",
            "end_date", "is_active", "created_at", "updated_at"
        ],
        WS_TRANSACTIONS: [
            "txn_id", "txn_date", "store_id", "vendor_id", "item_id", "item_name",
            "txn_type", "qty", "unit", "base_qty", "unit_price", "amount",
            "ref_type", "ref_id", "note", "created_by", "created_at"
        ],
        WS_STOCKTAKES: [
            "stocktake_id", "stocktake_date", "store_id", "vendor_id", "status",
            "note", "created_by", "created_at", "updated_at"
        ],
        WS_STOCKTAKE_LINES: [
            "stocktake_line_id", "stocktake_id", "store_id", "vendor_id", "item_id", "item_name",
            "stock_qty", "stock_unit", "stock_unit_id", "base_qty",
            "suggested_order_qty", "order_qty", "order_unit_id", "note",
            "created_at", "updated_at"
        ],
        WS_PURCHASE_ORDERS: [
            "po_id", "po_date", "order_date", "expected_date", "store_id", "vendor_id",
            "status", "note", "created_by", "created_at", "updated_at"
        ],
        WS_PO_LINES: [
            "po_line_id", "po_id", "store_id", "vendor_id", "item_id", "item_name",
            "order_qty", "order_unit", "unit_id", "qty", "base_qty",
            "unit_price", "amount", "note", "created_at", "updated_at"
        ],
        WS_ROLES: [
            "role_id", "role_name", "role_name_zh", "role_level", "is_active", "created_at", "updated_at"
        ],
        WS_USERS: [
            "user_id", "account_code", "email", "display_name", "role_id",
            "store_scope", "is_active", "last_login_at", "created_at", "updated_at"
        ],
        WS_AUDIT_LOGS: [
            "audit_id", "ts", "user_id", "action", "table_name", "entity_id",
            "before_json", "after_json", "note"
        ],
        WS_SETTINGS: [
            "setting_key", "setting_value", "updated_at", "updated_by"
        ],
        WS_ID_SEQUENCES: [
            "key", "env", "prefix", "width", "next_value", "updated_at", "updated_by"
        ],
    }

    for ws_name, cols in required.items():
        ensure_ws_headers(ws_name, cols)

# ============================================================
# [C0] Master Data Load
# ============================================================
@st.cache_data(show_spinner=False)
def load_master_data():
    items = ensure_columns(read_ws(WS_ITEMS), [
        "item_id", "brand_id", "default_vendor_id", "item_name", "item_name_zh", "item_type",
        "category", "spec", "base_unit", "default_stock_unit", "default_order_unit",
        "orderable_units", "price", "is_active", "created_at", "updated_at"
    ])
    stores = ensure_columns(read_ws(WS_STORES), [
        "store_id", "brand_id", "store_name", "store_name_zh", "store_code",
        "is_active", "created_at", "updated_at"
    ])
    prices = ensure_columns(read_ws(WS_PRICES), [
        "price_id", "item_id", "unit_price", "price_unit", "effective_date",
        "end_date", "is_active", "created_at", "updated_at"
    ])
    return items, stores, prices


def normalize_items_df(items: pd.DataFrame) -> pd.DataFrame:
    items = ensure_columns(items.copy(), [
        "item_id", "brand_id", "default_vendor_id", "item_name", "item_name_zh", "item_type",
        "category", "spec", "base_unit", "default_stock_unit", "default_order_unit",
        "orderable_units", "price", "is_active", "created_at", "updated_at"
    ])
    items["item_type"] = items["item_type"].replace("", "ingredient")
    items["is_active"] = items["is_active"].replace("", "1")
    return items


def normalize_store_df(stores: pd.DataFrame) -> pd.DataFrame:
    stores = ensure_columns(stores.copy(), [
        "store_id", "brand_id", "store_name", "store_name_zh", "store_code",
        "is_active", "created_at", "updated_at"
    ])
    stores["is_active"] = stores["is_active"].replace("", "1")
    return stores


def normalize_price_df(prices: pd.DataFrame) -> pd.DataFrame:
    prices = ensure_columns(prices.copy(), [
        "price_id", "item_id", "unit_price", "price_unit", "effective_date",
        "end_date", "is_active", "created_at", "updated_at"
    ])
    prices["is_active"] = prices["is_active"].replace("", "1")
    return prices


def get_price_by_date(item_id: str, target_date: str, prices_df: pd.DataFrame, items_df: pd.DataFrame) -> float:
    item_id = _norm(item_id)
    target = pd.to_datetime(target_date, errors="coerce")

    if pd.isna(target):
        target = pd.Timestamp.today().normalize()

    if not prices_df.empty:
        sub = prices_df[
            (prices_df["item_id"].astype(str) == item_id) &
            (prices_df["is_active"].astype(str).replace("", "1") != "0")
        ].copy()

        if not sub.empty:
            sub["effective_date_parsed"] = pd.to_datetime(sub["effective_date"], errors="coerce")
            sub["end_date_parsed"] = pd.to_datetime(sub["end_date"], errors="coerce")

            sub = sub[
                sub["effective_date_parsed"].notna() &
                (sub["effective_date_parsed"] <= target) &
                (
                    sub["end_date_parsed"].isna() |
                    (sub["end_date_parsed"] >= target)
                )
            ].copy()

            if not sub.empty:
                sub = sub.sort_values("effective_date_parsed", ascending=False)
                return _safe_float(sub.iloc[0].get("unit_price"), 0.0)

    hit = items_df[items_df["item_id"].astype(str) == item_id]
    if not hit.empty:
        return _safe_float(hit.iloc[0].get("price"), 0.0)

    return 0.0

# ============================================================
# [C1] Transactions / History
# ============================================================
def load_txn_data():
    tx = ensure_columns(read_ws(WS_TRANSACTIONS), [
        "txn_id", "txn_date", "store_id", "vendor_id", "item_id", "item_name",
        "txn_type", "qty", "unit", "base_qty", "unit_price", "amount",
        "ref_type", "ref_id", "note", "created_by", "created_at"
    ])
    po = ensure_columns(read_ws(WS_PURCHASE_ORDERS), [
        "po_id", "po_date", "order_date", "expected_date", "store_id", "vendor_id",
        "status", "note", "created_by", "created_at", "updated_at"
    ])
    po_lines = ensure_columns(read_ws(WS_PO_LINES), [
        "po_line_id", "po_id", "store_id", "vendor_id", "item_id", "item_name",
        "order_qty", "order_unit", "unit_id", "qty", "base_qty",
        "unit_price", "amount", "note", "created_at", "updated_at"
    ])
    st_head = ensure_columns(read_ws(WS_STOCKTAKES), [
        "stocktake_id", "stocktake_date", "store_id", "vendor_id", "status",
        "note", "created_by", "created_at", "updated_at"
    ])
    st_lines = ensure_columns(read_ws(WS_STOCKTAKE_LINES), [
        "stocktake_line_id", "stocktake_id", "store_id", "vendor_id", "item_id", "item_name",
        "stock_qty", "stock_unit", "stock_unit_id", "base_qty",
        "suggested_order_qty", "order_qty", "order_unit_id", "note",
        "created_at", "updated_at"
    ])
    return tx, po, po_lines, st_head, st_lines


def current_stock_by_item(store_id: str) -> dict:
    tx, _, _, _, _ = load_txn_data()
    result = {}
    if tx.empty:
        return result

    sub = tx[tx["store_id"].astype(str) == str(store_id)].copy()
    if sub.empty:
        return result

    sub["base_qty_num"] = pd.to_numeric(sub["base_qty"], errors="coerce").fillna(0.0)
    grouped = sub.groupby(["item_id", "txn_type"], dropna=False)["base_qty_num"].sum().reset_index()

    for item_id in grouped["item_id"].dropna().unique():
        item_rows = grouped[grouped["item_id"] == item_id]
        stocktake_qty = item_rows.loc[item_rows["txn_type"] == "stocktake", "base_qty_num"].sum()
        purchase_qty = item_rows.loc[item_rows["txn_type"] == "purchase", "base_qty_num"].sum()
        adjust_in_qty = item_rows.loc[item_rows["txn_type"] == "adjust_in", "base_qty_num"].sum()
        adjust_out_qty = item_rows.loc[item_rows["txn_type"] == "adjust_out", "base_qty_num"].sum()
        usage_qty = item_rows.loc[item_rows["txn_type"] == "usage", "base_qty_num"].sum()
        sale_usage_qty = item_rows.loc[item_rows["txn_type"] == "sale_usage", "base_qty_num"].sum()

        result[item_id] = stocktake_qty + purchase_qty + adjust_in_qty - adjust_out_qty - usage_qty - sale_usage_qty

    return result


def latest_order_history(store_id: str, vendor_id: str, item_id: str) -> tuple[str, float, str]:
    tx, _, _, _, _ = load_txn_data()
    if tx.empty:
        return "-", 0.0, ""

    sub = tx[
        (tx["store_id"].astype(str) == str(store_id)) &
        (tx["vendor_id"].astype(str) == str(vendor_id)) &
        (tx["item_id"].astype(str) == str(item_id)) &
        (tx["txn_type"].astype(str) == "purchase")
    ].copy()

    if sub.empty:
        return "-", 0.0, ""

    sub["txn_date_parsed"] = pd.to_datetime(sub["txn_date"], errors="coerce")
    sub = sub.sort_values("txn_date_parsed", ascending=False)
    row = sub.iloc[0]
    return _norm(row.get("txn_date")) or "-", _safe_float(row.get("qty"), 0.0), _norm(row.get("unit"))


def get_usage_suggestion(store_id: str, item_id: str, days: int = 7) -> float:
    tx, _, _, _, _ = load_txn_data()
    if tx.empty:
        return 1.0

    sub = tx[
        (tx["store_id"].astype(str) == str(store_id)) &
        (tx["item_id"].astype(str) == str(item_id)) &
        (tx["txn_type"].astype(str).isin(["usage", "sale_usage"]))
    ].copy()

    if sub.empty:
        return 1.0

    sub["txn_date_parsed"] = pd.to_datetime(sub["txn_date"], errors="coerce")
    cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=days)
    sub = sub[sub["txn_date_parsed"] >= cutoff]

    if sub.empty:
        return 1.0

    sub["base_qty_num"] = pd.to_numeric(sub["base_qty"], errors="coerce").fillna(0.0)
    total_usage = sub["base_qty_num"].sum()
    avg_daily = total_usage / max(days, 1)
    return round(max(avg_daily, 1.0), 1)

# ============================================================
# [C2] ID Sequences
# ============================================================
def next_sequence_value(key_name: str, env: str = "prod") -> str:
    df = ensure_columns(read_ws(WS_ID_SEQUENCES), [
        "key", "env", "prefix", "width", "next_value", "updated_at", "updated_by"
    ])

    mask = (df["key"].astype(str) == str(key_name)) & (df["env"].astype(str).replace("", "prod") == env)
    ts = now_ts()

    if df.empty or mask.sum() == 0:
        default_prefix_map = {
            "stocktake_id": "STK",
            "stocktake_line_id": "STL",
            "po_id": "PO",
            "po_line_id": "POL",
            "txn_id": "TXN",
            "audit_id": "AUD",
        }
        prefix = default_prefix_map.get(key_name, key_name.upper())
        width = 4
        next_value = 2

        new_row = pd.DataFrame([{
            "key": key_name,
            "env": env,
            "prefix": prefix,
            "width": width,
            "next_value": next_value,
            "updated_at": ts,
            "updated_by": DEFAULT_ACCOUNT_CODE,
        }])

        out = pd.concat([df, new_row], ignore_index=True) if not df.empty else new_row
        write_ws_df(WS_ID_SEQUENCES, out)
        return f"{prefix}_{str(1).zfill(width)}"

    idx = df[mask].index[0]
    prefix = _norm(df.at[idx, "prefix"]) or key_name.upper()
    width = _safe_int(df.at[idx, "width"], 4)
    current_next = _safe_int(df.at[idx, "next_value"], 1)

    generated = f"{prefix}_{str(current_next).zfill(width)}"
    df.at[idx, "next_value"] = current_next + 1
    df.at[idx, "updated_at"] = ts
    df.at[idx, "updated_by"] = DEFAULT_ACCOUNT_CODE
    write_ws_df(WS_ID_SEQUENCES, df)
    return generated

# ============================================================
# [D0] Settings
# ============================================================
def load_settings_dict() -> dict:
    df = ensure_columns(read_ws(WS_SETTINGS), ["setting_key", "setting_value", "updated_at", "updated_by"])
    if df.empty:
        return {
            "system_name": "ORIVIA OMS",
            "theme_mode": "system",
            "currency": "NT$",
            "default_suggestion_days": "7",
            "history_days": "30",
            "show_history": "1",
            "show_analysis": "1",
            "show_settings": "1",
        }

    out = {}
    for _, row in df.iterrows():
        key = _norm(row.get("setting_key"))
        value = _norm(row.get("setting_value"))
        if key:
            out[key] = value

    defaults = {
        "system_name": "ORIVIA OMS",
        "theme_mode": "system",
        "currency": "NT$",
        "default_suggestion_days": "7",
        "history_days": "30",
        "show_history": "1",
        "show_analysis": "1",
        "show_settings": "1",
    }
    for k, v in defaults.items():
        out.setdefault(k, v)

    return out


def save_settings_dict(settings: dict):
    ts = now_ts()
    rows = []
    for k, v in settings.items():
        rows.append([k, v, ts, DEFAULT_ACCOUNT_CODE])
    df = pd.DataFrame(rows, columns=["setting_key", "setting_value", "updated_at", "updated_by"])
    write_ws_df(WS_SETTINGS, df)

# ============================================================
# [D1] Sidebar
# ============================================================
def render_sidebar(stores_df: pd.DataFrame, settings: dict):
    st.sidebar.title(settings.get("system_name", "ORIVIA OMS"))
    st.sidebar.caption(APP_VERSION)

    store_options = []
    store_name_map = {}

    if not stores_df.empty:
        active = stores_df[stores_df["is_active"].astype(str) != "0"].copy()
        for _, row in active.iterrows():
            sid = _norm(row.get("store_id"))
            sname = _norm(row.get("store_name_zh")) or _norm(row.get("store_name")) or sid
            if sid:
                store_options.append(sid)
                store_name_map[sid] = sname

    if not store_options:
        st.sidebar.warning("目前沒有可用分店資料")
        selected_store = ""
    else:
        selected_store = st.sidebar.selectbox(
            "選擇分店",
            options=store_options,
            format_func=lambda x: store_name_map.get(x, x),
        )

    pages = ["叫貨 / 庫存"]
    if settings.get("show_history", "1") == "1":
        pages.append("歷史紀錄")
    if settings.get("show_analysis", "1") == "1":
        pages.append("分析報表")
    if settings.get("show_settings", "1") == "1":
        pages.append("設定")

    page = st.sidebar.radio("頁面", pages)
    return selected_store, page, store_name_map

# ============================================================
# [E0] Order Entry Page
# ============================================================
def render_order_entry(selected_store: str, items_df: pd.DataFrame, prices_df: pd.DataFrame, settings: dict):
    st.title("叫貨 / 庫存")
    st.caption("同頁完成庫存盤點與叫貨輸入")

    if not selected_store:
        st.info("請先選擇分店")
        return

    suggestion_days = _safe_int(settings.get("default_suggestion_days", "7"), 7)

    items_df = normalize_items_df(items_df)
    items_df = items_df[
        (items_df["item_type"].astype(str) == "ingredient") &
        (items_df["is_active"].astype(str) != "0")
    ].copy()

    if items_df.empty:
        st.warning("目前沒有原料品項資料")
        return

    vendor_options = sorted([x for x in items_df["default_vendor_id"].astype(str).unique().tolist() if x])
    if not vendor_options:
        st.warning("items 表沒有可用的 default_vendor_id")
        return

    selected_vendor = st.selectbox("選擇廠商", options=vendor_options)
    vendor_items = items_df[items_df["default_vendor_id"].astype(str) == str(selected_vendor)].copy()
    vendor_items = vendor_items.sort_values(by=["item_name_zh", "item_name", "item_id"])

    stock_map = current_stock_by_item(selected_store)
    meta_map = {}

    for _, row in vendor_items.iterrows():
        item_id = _norm(row.get("item_id"))
        base_unit = _norm(row.get("base_unit")) or _norm(row.get("default_stock_unit")) or ""
        stock_unit = _norm(row.get("default_stock_unit")) or base_unit
        order_unit = _norm(row.get("default_order_unit")) or base_unit
        item_name = item_display_name(row)
        unit_price = get_price_by_date(item_id, _today_str(), prices_df, items_df)
        hist_date, hist_qty, hist_unit = latest_order_history(selected_store, selected_vendor, item_id)
        suggestion = get_usage_suggestion(selected_store, item_id, suggestion_days)

        meta_map[item_id] = {
            "item_name": item_name,
            "base_unit": base_unit,
            "stock_unit": stock_unit,
            "order_unit": order_unit,
            "orderable_units": parse_list_field(row.get("orderable_units", ""), order_unit),
            "current_stock_qty": round(stock_map.get(item_id, 0.0), 1),
            "unit_price": unit_price,
            "hist_date": hist_date,
            "hist_qty": hist_qty,
            "hist_unit": hist_unit,
            "suggestion": suggestion,
        }

    entry_date = st.date_input("日期", value=date.today())
    note = st.text_input("備註", value="")

    with st.form("order_entry_form"):
        submit_rows = []

        for _, row in vendor_items.iterrows():
            item_id = _norm(row.get("item_id"))
            meta = meta_map[item_id]

            st.markdown("<div class='orivia-card'>", unsafe_allow_html=True)
            st.markdown(f"<div class='orivia-item-name'>{meta['item_name']}</div>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='orivia-sub'>單價 {DEFAULT_CURRENCY}{meta['unit_price']:.0f} ／ 上次叫貨 {meta['hist_date']} {meta['hist_qty']:.1f}{meta['hist_unit']} ／ 建議 {meta['suggestion']:.1f}</div>",
                unsafe_allow_html=True,
            )

            col1, col2, col3, col4 = st.columns([1.2, 0.7, 1.2, 0.8], gap="small")

            stock_qty = col1.number_input(
                "庫存",
                min_value=0.0,
                value=float(meta["current_stock_qty"]),
                step=0.1,
                format="%.1f",
                key=f"stock_{item_id}",
                label_visibility="collapsed",
            )
            col2.caption(meta["stock_unit"] or meta["base_unit"])

            order_qty = col3.number_input(
                "進貨",
                min_value=0.0,
                value=0.0,
                step=0.1,
                format="%.1f",
                key=f"order_{item_id}",
                label_visibility="collapsed",
            )
            order_unit = col4.selectbox(
                "進貨單位",
                options=meta["orderable_units"],
                index=meta["orderable_units"].index(meta["order_unit"]) if meta["order_unit"] in meta["orderable_units"] else 0,
                key=f"order_unit_{item_id}",
                label_visibility="collapsed",
            )

            submit_rows.append({
                "item_id": item_id,
                "item_name": meta["item_name"],
                "stock_qty": round(stock_qty, 1),
                "stock_unit": meta["stock_unit"],
                "base_unit": meta["base_unit"],
                "order_qty": round(order_qty, 1),
                "order_unit": order_unit,
                "suggested_order_qty": meta["suggestion"],
                "unit_price": meta["unit_price"],
                "vendor_id": selected_vendor,
            })

            st.markdown("</div>", unsafe_allow_html=True)

        submitted = st.form_submit_button("送出")

    if submitted:
        save_order_entry(
            store_id=selected_store,
            txn_date=entry_date.isoformat(),
            note=note,
            rows=submit_rows,
        )
        st.success("已完成寫入：庫存與叫貨紀錄已更新")
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()


def save_order_entry(store_id: str, txn_date: str, note: str, rows: list[dict]):
    created_at = now_ts()

    stocktake_id = next_sequence_value("stocktake_id")
    po_id = next_sequence_value("po_id")

    stocktake_head_rows = [[
        stocktake_id,
        txn_date,
        store_id,
        rows[0]["vendor_id"] if rows else "",
        "submitted",
        note,
        DEFAULT_ACCOUNT_CODE,
        created_at,
        created_at,
    ]]

    po_needed = any(_safe_float(r["order_qty"], 0.0) > 0 for r in rows)
    po_head_rows = []
    if po_needed:
        vendors_used = sorted(set([r["vendor_id"] for r in rows if _safe_float(r["order_qty"], 0.0) > 0]))
        for vendor_id in vendors_used:
            po_head_rows.append([
                po_id,
                txn_date,
                txn_date,
                "",
                store_id,
                vendor_id,
                "submitted",
                note,
                DEFAULT_ACCOUNT_CODE,
                created_at,
                created_at,
            ])

    stocktake_line_rows = []
    po_line_rows = []
    txn_rows = []

    for r in rows:
        item_id = r["item_id"]
        item_name = r["item_name"]
        vendor_id = r["vendor_id"]
        stock_qty = _safe_float(r["stock_qty"], 0.0)
        order_qty = _safe_float(r["order_qty"], 0.0)
        stock_unit = _norm(r["stock_unit"])
        order_unit = _norm(r["order_unit"])
        unit_price = _safe_float(r["unit_price"], 0.0)
        suggestion = _safe_float(r["suggested_order_qty"], 0.0)

        # 暫時未接 unit_conversions，先 1:1
        stock_base_qty = stock_qty
        order_base_qty = order_qty

        stocktake_line_id = next_sequence_value("stocktake_line_id")
        stocktake_line_rows.append([
            stocktake_line_id,
            stocktake_id,
            store_id,
            vendor_id,
            item_id,
            item_name,
            stock_qty,
            stock_unit,
            "",
            stock_base_qty,
            suggestion,
            order_qty,
            "",
            note,
            created_at,
            created_at,
        ])

        txn_rows.append([
            next_sequence_value("txn_id"),
            txn_date,
            store_id,
            vendor_id,
            item_id,
            item_name,
            "stocktake",
            stock_qty,
            stock_unit,
            stock_base_qty,
            unit_price,
            stock_qty * unit_price,
            "stocktake",
            stocktake_id,
            note,
            DEFAULT_ACCOUNT_CODE,
            created_at,
        ])

        if order_qty > 0:
            po_line_id = next_sequence_value("po_line_id")
            amount = order_qty * unit_price

            po_line_rows.append([
                po_line_id,
                po_id,
                store_id,
                vendor_id,
                item_id,
                item_name,
                order_qty,
                order_unit,
                "",
                order_qty,
                order_base_qty,
                unit_price,
                amount,
                note,
                created_at,
                created_at,
            ])

            txn_rows.append([
                next_sequence_value("txn_id"),
                txn_date,
                store_id,
                vendor_id,
                item_id,
                item_name,
                "purchase",
                order_qty,
                order_unit,
                order_base_qty,
                unit_price,
                amount,
                "purchase_order",
                po_id,
                note,
                DEFAULT_ACCOUNT_CODE,
                created_at,
            ])

    append_rows(WS_STOCKTAKES, stocktake_head_rows)
    append_rows(WS_STOCKTAKE_LINES, stocktake_line_rows)
    append_rows(WS_PURCHASE_ORDERS, po_head_rows)
    append_rows(WS_PO_LINES, po_line_rows)
    append_rows(WS_TRANSACTIONS, txn_rows)

# ============================================================
# [E1] History Page
# ============================================================
def render_history_page(selected_store: str):
    st.title("歷史紀錄")
    st.caption("查看庫存盤點、叫貨與交易紀錄")

    if not selected_store:
        st.info("請先選擇分店")
        return

    tx, _, po_lines, _, st_lines = load_txn_data()
    tab1, tab2, tab3 = st.tabs(["交易紀錄", "叫貨紀錄", "庫存紀錄"])

    with tab1:
        sub = tx[tx["store_id"].astype(str) == str(selected_store)].copy()
        if sub.empty:
            st.info("目前沒有交易資料")
        else:
            item_options = ["全部"] + sorted(sub["item_name"].astype(str).replace("", pd.NA).dropna().unique().tolist())
            txn_types = ["全部"] + sorted(sub["txn_type"].astype(str).replace("", pd.NA).dropna().unique().tolist())

            c1, c2, c3 = st.columns([1, 1, 2])
            sel_type = c1.selectbox("類型", txn_types)
            sel_item = c2.selectbox("品項", item_options)
            keyword = c3.text_input("關鍵字", value="")

            if sel_type != "全部":
                sub = sub[sub["txn_type"].astype(str) == sel_type]
            if sel_item != "全部":
                sub = sub[sub["item_name"].astype(str) == sel_item]
            if keyword.strip():
                kw = keyword.strip().lower()
                sub = sub[sub.apply(lambda r: kw in str(r.to_dict()).lower(), axis=1)]

            sub["txn_date_parsed"] = pd.to_datetime(sub["txn_date"], errors="coerce")
            sub = sub.sort_values("txn_date_parsed", ascending=False)

            st.dataframe(
                sub[["txn_date", "item_name", "txn_type", "qty", "unit", "unit_price", "amount", "note"]],
                use_container_width=True,
                hide_index=True,
            )

    with tab2:
        sub = po_lines[po_lines["store_id"].astype(str) == str(selected_store)].copy()
        if sub.empty:
            st.info("目前沒有叫貨紀錄")
        else:
            sub["created_at_parsed"] = pd.to_datetime(sub["created_at"], errors="coerce")
            sub = sub.sort_values("created_at_parsed", ascending=False)
            st.dataframe(
                sub[["created_at", "vendor_id", "item_name", "order_qty", "order_unit", "unit_price", "amount", "po_id"]],
                use_container_width=True,
                hide_index=True,
            )

    with tab3:
        sub = st_lines[st_lines["store_id"].astype(str) == str(selected_store)].copy()
        if sub.empty:
            st.info("目前沒有庫存紀錄")
        else:
            sub["created_at_parsed"] = pd.to_datetime(sub["created_at"], errors="coerce")
            sub = sub.sort_values("created_at_parsed", ascending=False)
            st.dataframe(
                sub[["created_at", "vendor_id", "item_name", "stock_qty", "stock_unit", "stocktake_id"]],
                use_container_width=True,
                hide_index=True,
            )

# ============================================================
# [E2] Analysis Page
# ============================================================
def render_analysis_page(selected_store: str):
    st.title("分析報表")
    st.caption("報表模式：只保留查看與下載 PNG")

    if not selected_store:
        st.info("請先選擇分店")
        return

    tx, _, _, _, _ = load_txn_data()
    if tx.empty:
        st.info("目前沒有可分析的交易資料")
        return

    df = tx[tx["store_id"].astype(str) == str(selected_store)].copy()
    if df.empty:
        st.info("這間分店目前沒有資料")
        return

    df["txn_date_parsed"] = pd.to_datetime(df["txn_date"], errors="coerce")
    df["base_qty_num"] = pd.to_numeric(df["base_qty"], errors="coerce").fillna(0.0)
    df["amount_num"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)

    c1, c2 = st.columns([1, 1])
    txn_type_options = ["全部"] + sorted(df["txn_type"].astype(str).replace("", pd.NA).dropna().unique().tolist())
    vendor_options = ["全部"] + sorted(df["vendor_id"].astype(str).replace("", pd.NA).dropna().unique().tolist())
    sel_type = c1.selectbox("交易類型", txn_type_options)
    sel_vendor = c2.selectbox("廠商", vendor_options)

    if sel_type != "全部":
        df = df[df["txn_type"].astype(str) == sel_type]
    if sel_vendor != "全部":
        df = df[df["vendor_id"].astype(str) == sel_vendor]

    total_qty = df["base_qty_num"].sum()
    total_amount = df["amount_num"].sum()
    total_rows = len(df)

    k1, k2, k3 = st.columns(3)
    k1.metric("總數量", _fmt_num(total_qty, 1))
    k2.metric("總金額", _fmt_money(total_amount))
    k3.metric("筆數", f"{total_rows:,}")

    tab1, tab2 = st.tabs(["明細", "趨勢"])

    with tab1:
        show_cols = ["txn_date", "vendor_id", "item_name", "txn_type", "qty", "unit", "amount"]
        st.dataframe(df[show_cols].sort_values("txn_date_parsed", ascending=False), use_container_width=True, hide_index=True)

    with tab2:
        if not HAS_PLOTLY:
            st.warning("目前環境沒有 Plotly，無法顯示圖表")
            return

        trend_src = df.dropna(subset=["txn_date_parsed"]).copy()
        trend = trend_src.groupby(trend_src["txn_date_parsed"].dt.date).agg(
            total_qty=("base_qty_num", "sum"),
            total_amount=("amount_num", "sum")
        ).reset_index()
        trend.columns = ["date", "total_qty", "total_amount"]

        if not trend.empty:
            fig1 = px.line(trend, x="date", y="total_amount", title="每日金額趨勢")
            fig1.update_layout(dragmode=False)
            st.plotly_chart(fig1, use_container_width=True, config=PLOTLY_CONFIG)

        top20 = df.groupby(["item_name"], dropna=False).agg(
            total_amount=("amount_num", "sum"),
            total_qty=("base_qty_num", "sum")
        ).reset_index().sort_values("total_amount", ascending=False).head(20)

        if not top20.empty:
            fig2 = px.bar(top20, x="item_name", y="total_amount", title="Top 20 品項金額")
            fig2.update_layout(dragmode=False)
            st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)

# ============================================================
# [E3] Settings Page
# ============================================================
def render_settings_page(settings: dict):
    st.title("設定")
    st.caption("主系統集中設定，影響所有分店")

    theme_options = ["system", "light", "dark"]
    current_theme = settings.get("theme_mode", "system")
    if current_theme not in theme_options:
        current_theme = "system"

    with st.form("settings_form"):
        system_name = st.text_input("系統名稱", value=settings.get("system_name", "ORIVIA OMS"))
        theme_mode = st.selectbox("外觀模式", theme_options, index=theme_options.index(current_theme))
        currency = st.text_input("幣別", value=settings.get("currency", "NT$"))
        suggestion_days = st.number_input(
            "建議數量計算天數",
            min_value=1,
            max_value=90,
            value=_safe_int(settings.get("default_suggestion_days", "7"), 7),
            step=1,
        )
        history_days = st.number_input(
            "歷史頁預設天數",
            min_value=1,
            max_value=365,
            value=_safe_int(settings.get("history_days", "30"), 30),
            step=1,
        )

        st.markdown("### 頁面開關")
        show_analysis = st.checkbox("開啟分析報表", value=settings.get("show_analysis", "1") == "1")
        show_history = st.checkbox("開啟歷史紀錄", value=settings.get("show_history", "1") == "1")
        show_settings = st.checkbox("開啟設定頁", value=settings.get("show_settings", "1") == "1")

        submitted = st.form_submit_button("儲存設定")

    if submitted:
        new_settings = {
            "system_name": system_name,
            "theme_mode": theme_mode,
            "currency": currency,
            "default_suggestion_days": str(suggestion_days),
            "history_days": str(history_days),
            "show_analysis": "1" if show_analysis else "0",
            "show_history": "1" if show_history else "0",
            "show_settings": "1" if show_settings else "0",
        }
        save_settings_dict(new_settings)
        st.success("設定已儲存")
        st.rerun()

    st.markdown("### 目前設定摘要")
    st.json(settings)

# ============================================================
# [Z0] Main
# ============================================================
def main():
    # bootstrap_if_needed()
    settings = load_settings_dict()

    global DEFAULT_CURRENCY
    DEFAULT_CURRENCY = settings.get("currency", "NT$")

    items_df, stores_df, prices_df = load_master_data()
    items_df = normalize_items_df(items_df)
    stores_df = normalize_store_df(stores_df)
    prices_df = normalize_price_df(prices_df)

    selected_store, page, _ = render_sidebar(stores_df, settings)

    if page == "叫貨 / 庫存":
        render_order_entry(selected_store, items_df, prices_df, settings)
    elif page == "歷史紀錄":
        render_history_page(selected_store)
    elif page == "分析報表":
        render_analysis_page(selected_store)
    elif page == "設定":
        render_settings_page(settings)

if __name__ == "__main__":
    main()
