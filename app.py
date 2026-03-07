import streamlit as st import pandas as pd import gspread from oauth2client.service_account import ServiceAccountCredentials from datetime import date, datetime, timedelta from pathlib import Path import math

============================================================

[A0] Page Config

============================================================

st.set_page_config( page_title="ORIVIA OMS", page_icon="📦", layout="wide", initial_sidebar_state="expanded", )

============================================================

[A1] Optional Plotly

============================================================

try: import plotly.express as px HAS_PLOTLY = True except Exception: HAS_PLOTLY = False

PLOTLY_CONFIG = { "displayModeBar": True, "displaylogo": False, "scrollZoom": False, "doubleClick": False, "staticPlot": False, "modeBarButtonsToRemove": [ "zoom2d", "pan2d", "select2d", "lasso2d", "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d", "hoverClosestCartesian", "hoverCompareCartesian", "toggleSpikelines" ], "toImageButtonOptions": { "format": "png", "filename": "orivia_report", "scale": 2, }, }

============================================================

[A2] Config - 常改的地方

============================================================

SHEET_ID = "1c9twPCyOumPKSau5xgUShJJAG-D9aaZBhK2FWBl2zwc" DB_SHEET_ID = SHEET_ID

CSV_ITEMS = Path("品項總覽.xlsx - 品項.csv") CSV_STORE = Path("品項總覽.xlsx - 分店.csv") CSV_PRICE = Path("品項總覽.xlsx - 價格歷史.csv")

WS_TRANSACTIONS = "transactions" WS_PURCHASE_ORDERS = "purchase_orders" WS_PO_LINES = "purchase_order_lines" WS_STOCKTAKES = "stocktakes" WS_STOCKTAKE_LINES = "stocktake_lines" WS_SETTINGS = "settings"

DEFAULT_BRAND = "BRAND_000001" DEFAULT_USER = "ADMIN_01" DEFAULT_CURRENCY = "NT$" APP_VERSION = "OMS Full v1"

============================================================

[A3] CSS - 手機版與輸入框壓縮

============================================================

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

/* 移除 number_input 的 stepper */
div[data-testid="stNumberInput"] button {
    display: none !important;
}

/* selectbox 壓縮 */
div[data-baseweb="select"] > div {
    min-height: 36px !important;
}

div[data-baseweb="select"] span {
    font-size: 0.9rem !important;
}

/* caption 更乾淨 */
[data-testid="stCaptionContainer"] {
    margin-top: -0.25rem !important;
}

/* 行卡片 */
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

.orivia-divider {
    height: 8px;
}

@media (max-width: 768px) {
  .block-container {
      padding-left: 0.7rem;
      padding-right: 0.7rem;
  }
}
</style>""" st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

============================================================

[B0] Utilities

============================================================

def _norm(x): if x is None: return "" s = str(x).strip() if s.lower() == "nan": return "" return s

def _safe_float(x, default=0.0): try: if x is None or str(x).strip() == "": return default return float(x) except Exception: return default

def _safe_int(x, default=0): try: return int(float(x)) except Exception: return default

def _today_str(): return date.today().isoformat()

def _fmt_num(x, digits=1): try: v = float(x) if math.isnan(v): return f"{0:.{digits}f}" return f"{v:.{digits}f}" except Exception: return f"{0:.{digits}f}"

def _fmt_money(x): try: return f"{DEFAULT_CURRENCY}{float(x):,.0f}" except Exception: return f"{DEFAULT_CURRENCY}0"

def _to_date(x): try: return pd.to_datetime(x).date() except Exception: return None

def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame: for c in cols: if c not in df.columns: df[c] = "" return df

============================================================

[B1] Google Sheets

============================================================

@st.cache_resource(show_spinner=False) def get_gspread_client(): if "gcp" not in st.secrets: raise RuntimeError("找不到 st.secrets['gcp']，請先設定 Streamlit secrets。")

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp"]), scope)
return gspread.authorize(creds)

@st.cache_resource(show_spinner=False) def open_spreadsheet(sheet_id: str): gc = get_gspread_client() return gc.open_by_key(sheet_id)

def get_worksheet(ws_name: str): sh = open_spreadsheet(DB_SHEET_ID) try: return sh.worksheet(ws_name) except Exception: return sh.add_worksheet(title=ws_name, rows=1000, cols=50)

def read_ws(ws_name: str) -> pd.DataFrame: ws = get_worksheet(ws_name) values = ws.get_all_records() if not values: return pd.DataFrame() return pd.DataFrame(values)

def write_ws_df(ws_name: str, df: pd.DataFrame): ws = get_worksheet(ws_name) ws.clear() if df.empty: ws.update([[]]) return rows = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist() ws.update(rows)

def append_rows(ws_name: str, rows: list[list]): if not rows: return ws = get_worksheet(ws_name) ws.append_rows(rows, value_input_option="USER_ENTERED")

============================================================

[B2] Initial Sheet Bootstrap

============================================================

def bootstrap_if_needed(): required = { WS_TRANSACTIONS: [ "txn_id", "txn_date", "store_id", "vendor_id", "item_id", "item_name", "txn_type", "qty", "unit", "base_qty", "unit_price", "amount", "ref_type", "ref_id", "note", "created_by", "created_at" ], WS_PURCHASE_ORDERS: [ "po_id", "po_date", "store_id", "vendor_id", "status", "note", "created_by", "created_at" ], WS_PO_LINES: [ "po_line_id", "po_id", "store_id", "vendor_id", "item_id", "item_name", "order_qty", "order_unit", "base_qty", "unit_price", "amount", "created_at" ], WS_STOCKTAKES: [ "stocktake_id", "stocktake_date", "store_id", "vendor_id", "note", "created_by", "created_at" ], WS_STOCKTAKE_LINES: [ "stocktake_line_id", "stocktake_id", "store_id", "vendor_id", "item_id", "item_name", "stock_qty", "stock_unit", "base_qty", "created_at" ], WS_SETTINGS: [ "setting_key", "setting_value", "updated_at", "updated_by" ], }

for ws_name, cols in required.items():
    df = read_ws(ws_name)
    if df.empty:
        write_ws_df(ws_name, pd.DataFrame(columns=cols))
    else:
        df = ensure_columns(df, cols)
        write_ws_df(ws_name, df[cols])

============================================================

[C0] Master Data Load

============================================================

@st.cache_data(show_spinner=False) def load_csv_data(): items = pd.read_csv(CSV_ITEMS, dtype=str).fillna("") if CSV_ITEMS.exists() else pd.DataFrame() stores = pd.read_csv(CSV_STORE, dtype=str).fillna("") if CSV_STORE.exists() else pd.DataFrame() prices = pd.read_csv(CSV_PRICE, dtype=str).fillna("") if CSV_PRICE.exists() else pd.DataFrame() return items, stores, prices

def normalize_items_df(items: pd.DataFrame) -> pd.DataFrame: if items.empty: return items

need_cols = [
    "item_id", "brand_id", "default_vendor_id", "item_name", "item_name_zh", "item_type",
    "base_unit", "default_stock_unit", "default_order_unit", "orderable_units",
    "is_active", "price"
]
items = ensure_columns(items.copy(), need_cols)
items["item_type"] = items["item_type"].replace("", "ingredient")
items["is_active"] = items["is_active"].replace("", "1")
return items

def normalize_store_df(stores: pd.DataFrame) -> pd.DataFrame: if stores.empty: return stores need_cols = ["store_id", "store_name", "store_name_zh", "brand_id", "is_active"] stores = ensure_columns(stores.copy(), need_cols) stores["is_active"] = stores["is_active"].replace("", "1") return stores

def normalize_price_df(prices: pd.DataFrame) -> pd.DataFrame: if prices.empty: return prices need_cols = ["item_id", "unit_price", "effective_date", "end_date"] return ensure_columns(prices.copy(), need_cols)

def item_display_name(row) -> str: return _norm(row.get("item_name_zh")) or _norm(row.get("item_name")) or _norm(row.get("item_id"))

def parse_orderable_units(s: str, fallback: str) -> list[str]: s = _norm(s) if not s: return [fallback] if fallback else [] arr = [x.strip() for x in s.replace("/", ",").replace("、", ",").split(",") if x.strip()] if fallback and fallback not in arr: arr.insert(0, fallback) return arr or ([fallback] if fallback else [])

def get_price_by_date(item_id: str, target_date: str, prices_df: pd.DataFrame, items_df: pd.DataFrame) -> float: item_id = _norm(item_id) target = _to_date(target_date) or date.today()

if not prices_df.empty:
    sub = prices_df[prices_df["item_id"].astype(str) == item_id].copy()
    if not sub.empty:
        sub["effective_date_parsed"] = pd.to_datetime(sub["effective_date"], errors="coerce").dt.date
        sub["end_date_parsed"] = pd.to_datetime(sub["end_date"], errors="coerce").dt.date

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

if not items_df.empty:
    hit = items_df[items_df["item_id"].astype(str) == item_id]
    if not hit.empty:
        return _safe_float(hit.iloc[0].get("price"), 0.0)
return 0.0

============================================================

[C1] Current Stock / History Logic

============================================================

def load_txn_data(): tx = read_ws(WS_TRANSACTIONS) po = read_ws(WS_PURCHASE_ORDERS) po_lines = read_ws(WS_PO_LINES) st_head = read_ws(WS_STOCKTAKES) st_lines = read_ws(WS_STOCKTAKE_LINES) return tx, po, po_lines, st_head, st_lines

def current_stock_by_item(store_id: str) -> dict: tx, _, _, _, _ = load_txn_data() result = {} if tx.empty: return result

tx = ensure_columns(tx, ["store_id", "item_id", "txn_type", "base_qty"])
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

    result[item_id] = stocktake_qty + purchase_qty + adjust_in_qty - adjust_out_qty - usage_qty
return result

def latest_order_history(store_id: str, vendor_id: str, item_id: str) -> tuple[str, float, str]: tx, _, _, _, _ = load_txn_data() if tx.empty: return "-", 0.0, ""

tx = ensure_columns(tx, [
    "txn_date", "store_id", "vendor_id", "item_id", "txn_type",
    "qty", "unit", "base_qty"
])
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
date_str = _norm(row.get("txn_date")) or "-"
qty = _safe_float(row.get("qty"), 0.0)
unit = _norm(row.get("unit"))
return date_str, qty, unit

def get_usage_suggestion(store_id: str, item_id: str, days: int = 7) -> float: tx, _, _, _, _ = load_txn_data() if tx.empty: return 1.0

tx = ensure_columns(tx, ["txn_date", "store_id", "item_id", "txn_type", "base_qty"])
sub = tx[
    (tx["store_id"].astype(str) == str(store_id)) &
    (tx["item_id"].astype(str) == str(item_id)) &
    (tx["txn_type"].astype(str) == "usage")
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

============================================================

[C2] IDs / Audit

============================================================

def make_id(prefix: str) -> str: return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

def now_ts() -> str: return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

============================================================

[D0] Settings

============================================================

def load_settings_dict() -> dict: df = read_ws(WS_SETTINGS) if df.empty: return { "system_name": "ORIVIA OMS", "theme_mode": "system", "currency": "NT$", "default_suggestion_days": "7", "history_days": "30", "show_analysis": "1", "show_history": "1", "show_settings": "1", } df = ensure_columns(df, ["setting_key", "setting_value"]) out = {} for _, row in df.iterrows(): out[_norm(row.get("setting_key"))] = _norm(row.get("setting_value")) return out

def save_settings_dict(settings: dict): rows = [] ts = now_ts() for k, v in settings.items(): rows.append([k, v, ts, DEFAULT_USER]) df = pd.DataFrame(rows, columns=["setting_key", "setting_value", "updated_at", "updated_by"]) write_ws_df(WS_SETTINGS, df)

============================================================

[D1] Sidebar

============================================================

def render_sidebar(stores_df: pd.DataFrame, settings: dict): st.sidebar.title(settings.get("system_name", "ORIVIA OMS")) st.sidebar.caption(APP_VERSION)

store_options = []
store_name_map = {}
if not stores_df.empty:
    active = stores_df[stores_df["is_active"].astype(str) != "0"].copy()
    for _, row in active.iterrows():
        sid = _norm(row.get("store_id"))
        sname = _norm(row.get("store_name_zh")) or _norm(row.get("store_name")) or sid
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

============================================================

[E0] Order Entry Page

============================================================

def render_order_entry(selected_store: str, items_df: pd.DataFrame, prices_df: pd.DataFrame): st.title("叫貨 / 庫存") st.caption("同頁完成庫存盤點與叫貨輸入")

if not selected_store:
    st.info("請先選擇分店")
    return

items_df = normalize_items_df(items_df)
items_df = items_df[
    (items_df["item_type"].astype(str) == "ingredient") &
    (items_df["is_active"].astype(str) != "0")
].copy()

if items_df.empty:
    st.warning("目前沒有原料品項資料")
    return

vendor_options = sorted([x for x in items_df["default_vendor_id"].astype(str).unique().tolist() if x])
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
    suggestion = get_usage_suggestion(selected_store, item_id, 7)

    meta_map[item_id] = {
        "item_name": item_name,
        "base_unit": base_unit,
        "stock_unit": stock_unit,
        "order_unit": order_unit,
        "orderable_units": parse_orderable_units(row.get("orderable_units", ""), order_unit),
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
    st.success(        return v.date()

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




