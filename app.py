import streamlit as st 
import pandas as pd 
import gspread from oauth2client.service_account 
import ServiceAccountCredentials 
from datetime import date, datetime, timedelta 
from pathlib import Path 
import math

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
    st.success(

