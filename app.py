# ============================================================
# ORIVIA OMS Admin UI + Stocktake/Order (Single-file app.py)
# MOBILE FIX: 4欄同一行 + 數字一位小數 + 單位縮短(KG) + 移除 +/- 按鈕
# ============================================================

from __future__ import annotations

from pathlib import Path
from datetime import date
import time
import random
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ============================================================
# Fail-fast helpers
# ============================================================

def fail(msg: str):
    st.error(msg)
    st.stop()


def _now_ts() -> str:
    return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")


def _to_bool_str(v: bool) -> str:
    return "TRUE" if bool(v) else "FALSE"


def _parse_date(s) -> date | None:
    s = str(s).strip()
    if not s:
        return None
    try:
        return pd.to_datetime(s, errors="raise").date()
    except Exception:
        return None


def _extract_id_from_label(label: str) -> str:
    s = str(label).strip()
    if "(" in s and s.endswith(")"):
        inside = s.split("(")[-1].rstrip(")").strip()
        return inside if inside else s
    return s


# ============================================================
# Mobile / compact UI style  (key part)
# ============================================================

def apply_mobile_compact_style(max_width_px: int = 760):
    st.markdown(
        f"""
        <style>
        /* main container */
        [data-testid="stMainBlockContainer"] {{
            max-width: {max_width_px}px !important;
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
            margin: 0 auto !important;
        }}

        /* ========= 핵심：手機強制 columns 不折行 ========= */
        @media (max-width: 768px) {{
            [data-testid="stHorizontalBlock"] {{
                gap: 0.35rem !important;
                flex-wrap: nowrap !important;
                align-items: center !important;
            }}
            [data-testid="column"] {{
                min-width: 0 !important;
            }}
        }}

        /* ========= 數字輸入：固定寬度 + 右對齊 + 一位小數更好讀 ========= */
        div[data-testid="stNumberInput"] input {{
            width: 7.8ch !important;           /* 夠放 60.0 / 100.0 */
            max-width: 7.8ch !important;
            text-align: right !important;
            padding-right: 0.6rem !important;
        }}

        /* ========= Selectbox：盡量縮窄（單位只要一兩個字） ========= */
        div[data-testid="stSelectbox"] > div {{
            min-width: 5.2ch !important;
        }}

        /* ========= 移除 +/-（多版本DOM全封） ========= */
        /* 1) 舊版 steppers */
        div[data-testid="stNumberInputStepUp"],
        div[data-testid="stNumberInputStepDown"] {{
            display: none !important;
        }}
        /* 2) BaseWeb input buttons */
        div[data-baseweb="input"] button {{
            display: none !important;
        }}
        /* 3) aria-label / title variants */
        button[aria-label="Increment"],
        button[aria-label="Decrement"],
        button[aria-label="Increase"],
        button[aria-label="Decrease"],
        button[title="Increment"],
        button[title="Decrement"] {{
            display: none !important;
        }}
        /* 4) Some builds render +/- as svg icons inside buttons */
        div[data-testid="stNumberInput"] button {{
            display: none !important;
        }}

        /* tighten captions */
        .stCaption {{
            margin-top: -0.15rem !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header():
    st.title("ORIVIA OMS Admin UI")
    st.caption("MOBILE FIX: 4欄同一行 / 數字一位小數 / 單位縮短(KG) / 移除 +/-")


# ============================================================
# Sidebar: System Config
# ============================================================

def sidebar_system_config():
    with st.sidebar:
        st.subheader("System Config")

        sheet_id = st.text_input(
            "Sheet ID",
            value="1L1ogNjLWjjH8usMWC2JQowMMZkfD4zkuE-4UcgiTqXQ",
        ).strip()

        creds_path = st.text_input(
            "Service Account JSON Path (local only)",
            value="secrets/service_account.json",
        ).strip()

        env = st.text_input("ENV", value="prod").strip()
        audit_sheet = st.text_input("Audit Sheet", value="audit_log_test").strip()

        st.caption("✅ Streamlit Cloud 會自動用 st.secrets['gcp']，不看本機路徑。")

    return sheet_id, creds_path, env, audit_sheet


# ============================================================
# Actor + Role (方案1：UI選操作者)
# ============================================================

ACTOR_OPTIONS = ["OWNER", "ADMIN_01", "ADMIN_02", "ADMIN_03"]

ROLE_MAP = {
    "OWNER": "Owner",
    "ADMIN_01": "Admin",
    "ADMIN_02": "Admin",
    "ADMIN_03": "Admin",
}

ROLE_RANK = {"Owner": 3, "Admin": 2, "StoreManager": 1}


def role_of(actor_user_id: str) -> str:
    return ROLE_MAP.get(actor_user_id, "StoreManager")


def require_role(min_role: str, actor_role: str):
    if ROLE_RANK.get(actor_role, 0) < ROLE_RANK.get(min_role, 0):
        st.warning("⚠️ 權限不足，無法進入此頁面。")
        st.stop()


def sidebar_actor_selector():
    with st.sidebar:
        st.divider()
        st.subheader("Operator (方案1)")

        actor_user_id = st.selectbox(
            "操作者 actor_user_id",
            options=ACTOR_OPTIONS,
            index=0,
            key="actor_user_id",
        )

        actor_role = role_of(actor_user_id)
        st.caption(f"role: **{actor_role}**")

    return actor_user_id, actor_role


# ============================================================
# Google Sheets Repo + Rate limit backoff
# ============================================================

def _with_backoff(fn, *, tries: int = 6, base: float = 0.7, jitter: float = 0.25, desc: str = "gspread"):
    last_err = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last_err = e
            sleep_s = (base * (2 ** i)) * (1 + random.uniform(-jitter, jitter))
            time.sleep(max(0.2, sleep_s))
    raise last_err


class GoogleSheetsRepo:
    def __init__(self, sheet_id: str, creds_path: str | None = None):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        if "gcp" in st.secrets:
            creds = Credentials.from_service_account_info(st.secrets["gcp"], scopes=scopes)
        else:
            if not creds_path:
                raise FileNotFoundError("Missing creds_path (service_account.json path)")
            p = Path(creds_path)
            if not p.exists():
                raise FileNotFoundError(f"No such file: {p}")
            creds = Credentials.from_service_account_file(str(p), scopes=scopes)

        gc = gspread.authorize(creds)
        self.sh = _with_backoff(lambda: gc.open_by_key(sheet_id), desc="open_by_key")

    def get_ws(self, table: str):
        return _with_backoff(lambda: self.sh.worksheet(table), desc=f"worksheet:{table}")

    def fetch_all_values(self, table: str) -> list[list[str]]:
        ws = self.get_ws(table)
        return _with_backoff(lambda: ws.get_all_values(), desc=f"get_all_values:{table}")

    def append_row_dict(self, table: str, row: dict):
        ws = self.get_ws(table)
        values = self.fetch_all_values(table)
        if not values:
            raise ValueError(f"Table '{table}' has no header row.")
        header = values[0]

        missing = [c for c in header if c not in row]
        if missing:
            raise ValueError(f"Append '{table}' missing fields: {missing}")

        out = [row.get(c, "") for c in header]
        _with_backoff(lambda: ws.append_row(out, value_input_option="USER_ENTERED"), desc=f"append_row:{table}")

    def append_rows(self, table: str, rows: list[dict]):
        if not rows:
            return
        ws = self.get_ws(table)
        values = self.fetch_all_values(table)
        if not values:
            raise ValueError(f"Table '{table}' has no header row.")
        header = values[0]

        out_rows = []
        for row in rows:
            missing = [c for c in header if c not in row]
            if missing:
                raise ValueError(f"Append '{table}' missing fields: {missing}")
            out_rows.append([row.get(c, "") for c in header])

        _with_backoff(lambda: ws.append_rows(out_rows, value_input_option="USER_ENTERED"), desc=f"append_rows:{table}")

    def update_row(self, table: str, row_index_1based: int, new_row: dict):
        ws = self.get_ws(table)
        values = self.fetch_all_values(table)
        if not values:
            raise ValueError(f"Table '{table}' has no header row.")
        header = values[0]

        missing = [c for c in header if c not in new_row]
        if missing:
            raise ValueError(f"Update '{table}' missing fields: {missing}")

        row_values = [new_row.get(c, "") for c in header]
        start = gspread.utils.rowcol_to_a1(row_index_1based, 1)
        end = gspread.utils.rowcol_to_a1(row_index_1based, len(header))
        _with_backoff(lambda: ws.update(f"{start}:{end}", [row_values], value_input_option="USER_ENTERED"), desc=f"update:{table}")

    def update_fields_by_row(self, table: str, row_index_1based: int, patch: dict):
        ws = self.get_ws(table)
        values = self.fetch_all_values(table)
        if not values:
            raise ValueError(f"Table '{table}' has no header row.")
        header = values[0]

        row_vals = _with_backoff(lambda: ws.row_values(row_index_1based), desc=f"row_values:{table}")
        row_vals = row_vals + [""] * (len(header) - len(row_vals))
        cur = dict(zip(header, row_vals))

        for k, v in patch.items():
            if k in header:
                cur[k] = "" if v is None else str(v)

        for c in header:
            if c not in cur:
                cur[c] = ""

        self.update_row(table, row_index_1based, cur)


# ============================================================
# Cache layer
# ============================================================

@st.cache_resource(show_spinner=False)
def get_repo_cached(sheet_id: str, creds_path: str | None):
    return GoogleSheetsRepo(sheet_id=sheet_id, creds_path=creds_path)


@st.cache_data(show_spinner=False, ttl=120)
def cached_table_values(sheet_id: str, table: str, cache_bust: int) -> list[list[str]]:
    repo = get_repo_cached(sheet_id, None)
    return repo.fetch_all_values(table)


def bust_cache():
    st.session_state["cache_bust"] = int(st.session_state.get("cache_bust", 0)) + 1
    st.cache_data.clear()


def read_table(sheet_id: str, table: str) -> pd.DataFrame:
    bust = int(st.session_state.get("cache_bust", 0))
    values = cached_table_values(sheet_id, table, bust)
    if not values:
        return pd.DataFrame()
    header = values[0]
    rows = values[1:]
    return pd.DataFrame(rows, columns=header)


# ============================================================
# ID Generator (from id_sequences)
# ============================================================

def _make_id(prefix: str, width: int, n: int) -> str:
    return f"{prefix}{str(n).zfill(int(width))}"


def get_next_id(repo: GoogleSheetsRepo, key: str, env: str, actor_user_id: str) -> str:
    values = repo.fetch_all_values("id_sequences")
    if not values or len(values) < 2:
        raise ValueError("id_sequences is empty or missing header.")

    header = values[0]
    rows = values[1:]

    required = {"key", "env", "prefix", "width", "next_value"}
    if not required.issubset(set(header)):
        raise ValueError(f"id_sequences missing columns: {sorted(list(required - set(header)))}")

    df = pd.DataFrame(rows, columns=header)
    hit = df[(df["key"] == key) & (df["env"] == env)]
    if hit.empty:
        raise ValueError(f"id_sequences not found for key='{key}', env='{env}'")

    rec = hit.iloc[0].to_dict()
    prefix = str(rec["prefix"])
    width = int(rec["width"])
    next_value = int(rec["next_value"])

    new_id = _make_id(prefix, width, next_value)
    sheet_row_index = int(hit.index[0]) + 2

    updated = rec.copy()
    updated["next_value"] = str(next_value + 1)
    if "updated_at" in updated:
        updated["updated_at"] = _now_ts()
    if "updated_by" in updated:
        updated["updated_by"] = actor_user_id

    for c in header:
        if c not in updated:
            updated[c] = ""

    repo.update_row("id_sequences", sheet_row_index, updated)
    bust_cache()
    return new_id


# ============================================================
# Units: UI顯示名（公斤->KG） + 寫回 unit_id
# ============================================================

def _unit_ui_name(unit_name: str) -> str:
    name = str(unit_name).strip()
    if name == "公斤":
        return "KG"
    return name


def build_unit_ui_options(units_df: pd.DataFrame) -> tuple[list[str], dict[str, str], dict[str, str]]:
    """
    Returns:
      - ui_options: ["KG", "包", ...]
      - ui_to_unit_id: {"KG": "UNIT_000003", ...}
      - unit_id_to_ui: {"UNIT_000003": "KG", ...}
    """
    if units_df is None or units_df.empty:
        return ["(未設定)"], {"(未設定)": ""}, {"": "(未設定)"}

    df = units_df.copy()
    if "is_active" in df.columns:
        df = df[df["is_active"].astype(str).str.upper() == "TRUE"]

    ui_options: list[str] = []
    ui_to_unit_id: dict[str, str] = {}
    unit_id_to_ui: dict[str, str] = {}

    for _, r in df.iterrows():
        uid = str(r.get("unit_id", "")).strip()
        nm = str(r.get("unit_name", "")).strip()
        if not uid:
            continue
        ui = _unit_ui_name(nm) if nm else uid

        # UI 名稱可能重複（例如你未來可能有兩個「包」），先採用第一個
        if ui not in ui_to_unit_id:
            ui_options.append(ui)
            ui_to_unit_id[ui] = uid
        unit_id_to_ui[uid] = ui

    if not ui_options:
        return ["(未設定)"], {"(未設定)": ""}, {"": "(未設定)"}

    return ui_options, ui_to_unit_id, unit_id_to_ui


# ============================================================
# Prices
# ============================================================

def get_price_today(sheet_id: str, item_id: str, target_date: date) -> float:
    df = read_table(sheet_id, "prices")
    if df.empty:
        return 0.0

    need = {"item_id", "unit_price", "effective_date"}
    if not need.issubset(set(df.columns)):
        return 0.0

    tmp = df.copy()
    tmp["item_id"] = tmp["item_id"].astype(str).str.strip()
    tmp["unit_price"] = pd.to_numeric(tmp["unit_price"], errors="coerce").fillna(0.0)
    tmp["__eff"] = tmp["effective_date"].apply(_parse_date)
    tmp["__end"] = tmp["end_date"].apply(_parse_date) if "end_date" in tmp.columns else None
    tmp["__active"] = (
        tmp["is_active"].apply(lambda x: (str(x).strip() == "" or str(x).strip().upper() == "TRUE"))
        if "is_active" in tmp.columns
        else True
    )

    t = target_date
    rows = tmp[(tmp["item_id"] == str(item_id).strip()) & (tmp["__active"]) & (tmp["__eff"].notna())].copy()
    if rows.empty:
        return 0.0

    def _covers(r):
        eff = r["__eff"]
        end = r["__end"] if "__end" in r and pd.notna(r["__end"]) else None
        if eff is None:
            return False
        if eff > t:
            return False
        if end is None:
            return True
        return end >= t

    rows = rows[rows.apply(_covers, axis=1)]
    if rows.empty:
        return 0.0

    rows = rows.sort_values("__eff", ascending=True)
    return float(rows.iloc[-1]["unit_price"])


# ============================================================
# Stocktake/Order UI
# ============================================================

def render_item_block_mobile(
    *,
    item_id: str,
    item_name_zh: str,
    price_today: float,
    last_order_qty: float | None,
    suggest_qty: float | None,
    default_stock_unit_ui: str,
    default_order_unit_ui: str,
    unit_ui_options: list[str],
):
    # 第一行：品名 + 3資訊
    st.markdown(f"**{item_name_zh}**")
    last_txt = "—" if last_order_qty is None else f"{last_order_qty:.1f}"
    sugg_txt = "—" if suggest_qty is None else f"{suggest_qty:.1f}"
    st.caption(f"單價：{price_today:.2f} ｜ 上次叫貨：{last_txt} ｜ 建議：{sugg_txt}")

    # 第二行：4欄一定同一行（手機強制 nowrap）
    c1, c2, c3, c4 = st.columns([1.35, 0.75, 1.35, 0.75], gap="small")

    with c1:
        stock_qty = st.number_input(
            "庫存",
            min_value=0.0,
            step=0.5,
            value=0.0,
            format="%.1f",                    # ✅ 一位小數
            key=f"stk_qty__{item_id}",
            label_visibility="collapsed",
        )

    with c2:
        idx = unit_ui_options.index(default_stock_unit_ui) if default_stock_unit_ui in unit_ui_options else 0
        stock_unit_ui = st.selectbox(
            "庫單位",
            options=unit_ui_options,
            index=idx,
            key=f"stk_unit__{item_id}",
            label_visibility="collapsed",
        )

    with c3:
        order_qty = st.number_input(
            "進貨",
            min_value=0.0,
            step=0.5,
            value=0.0,
            format="%.1f",                    # ✅ 一位小數
            key=f"ord_qty__{item_id}",
            label_visibility="collapsed",
        )

    with c4:
        idx2 = unit_ui_options.index(default_order_unit_ui) if default_order_unit_ui in unit_ui_options else 0
        order_unit_ui = st.selectbox(
            "進單位",
            options=unit_ui_options,
            index=idx2,
            key=f"ord_unit__{item_id}",
            label_visibility="collapsed",
        )

    return float(stock_qty), stock_unit_ui, float(order_qty), order_unit_ui


def page_stocktake_order(repo: GoogleSheetsRepo, sheet_id: str, env: str, actor_user_id: str):
    require_role("Admin", role_of(actor_user_id))

    apply_mobile_compact_style(max_width_px=760)

    st.subheader("點貨 / 叫貨")
    st.caption("手機：品名一行；輸入一行（庫+單位 / 進+單位 同一行）。")

    # Store selection
    stores_df = read_table(sheet_id, "stores")
    store_opts = []
    if not stores_df.empty and "store_id" in stores_df.columns:
        if "store_name" in stores_df.columns:
            for _, r in stores_df.iterrows():
                sid = str(r.get("store_id", "")).strip()
                sname = str(r.get("store_name", "")).strip()
                if sid:
                    store_opts.append(f"{sname} ({sid})" if sname else sid)
        else:
            store_opts = [str(x).strip() for x in stores_df["store_id"].tolist() if str(x).strip()]

    if not store_opts:
        store_opts = ["STORE_000001 (default)"]

    colA, colB = st.columns([2, 1])
    with colA:
        store_label = st.selectbox("分店", options=store_opts, index=0)
    with colB:
        record_date = st.date_input("日期", value=date.today())

    store_id = _extract_id_from_label(store_label)

    # Vendor filter
    vendors_df = read_table(sheet_id, "vendors")
    vendor_opts = ["(全部廠商)"]
    if not vendors_df.empty and "vendor_id" in vendors_df.columns:
        if "is_active" in vendors_df.columns:
            vendors_df = vendors_df[vendors_df["is_active"].astype(str).str.upper() == "TRUE"]
        if "vendor_name" in vendors_df.columns:
            vendor_opts += [
                f"{str(r.get('vendor_name','')).strip()} ({str(r.get('vendor_id','')).strip()})"
                for _, r in vendors_df.iterrows()
                if str(r.get("vendor_id", "")).strip()
            ]
        else:
            vendor_opts += [str(x).strip() for x in vendors_df["vendor_id"].tolist() if str(x).strip()]

    vendor_label = st.selectbox("廠商（可先選，方便分段點貨）", options=vendor_opts, index=0)
    vendor_id = "" if vendor_label == "(全部廠商)" else _extract_id_from_label(vendor_label)

    # Units UI
    units_df = read_table(sheet_id, "units")
    unit_ui_options, ui_to_unit_id, unit_id_to_ui = build_unit_ui_options(units_df)

    # Items list
    items_df = read_table(sheet_id, "items")
    if items_df.empty:
        st.warning("items 沒有資料，請先建立品項。")
        return

    if "is_active" in items_df.columns:
        items_df = items_df[items_df["is_active"].astype(str).str.upper() == "TRUE"]

    if vendor_id and "vendor_id" in items_df.columns:
        items_df = items_df[items_df["vendor_id"].astype(str).str.strip() == vendor_id]

    if items_df.empty:
        st.info("此條件下沒有可用品項。")
        return

    # 只顯示中文品名
    def _item_name_zh(r):
        zh = str(r.get("item_name_zh", "")).strip() if "item_name_zh" in items_df.columns else ""
        if zh:
            return zh
        nm = str(r.get("item_name", "")).strip() if "item_name" in items_df.columns else ""
        return nm if nm else str(r.get("item_id", "")).strip()

    st.divider()

    with st.form("stocktake_order_form", clear_on_submit=False):
        rows_out = []

        for _, r in items_df.iterrows():
            item_id = str(r.get("item_id", "")).strip()
            if not item_id:
                continue

            item_name = _item_name_zh(r)

            # defaults from item master: stored as unit_id
            stock_unit_id = str(r.get("stock_unit", "")).strip() if "stock_unit" in items_df.columns else ""
            order_unit_id = str(r.get("order_unit", "")).strip() if "order_unit" in items_df.columns else ""

            default_stock_ui = unit_id_to_ui.get(stock_unit_id, unit_ui_options[0] if unit_ui_options else "(未設定)")
            default_order_ui = unit_id_to_ui.get(order_unit_id, unit_ui_options[0] if unit_ui_options else "(未設定)")

            price_today = float(get_price_today(sheet_id, item_id, record_date) or 0.0)

            # ======= TEST STAGE =======
            last_order_qty = None   # 顯示 —
            suggest_qty = 1.0       # 先固定 1
            # =========================

            stock_qty, stock_unit_ui, order_qty, order_unit_ui = render_item_block_mobile(
                item_id=item_id,
                item_name_zh=item_name,
                price_today=price_today,
                last_order_qty=last_order_qty,
                suggest_qty=suggest_qty,
                default_stock_unit_ui=default_stock_ui,
                default_order_unit_ui=default_order_ui,
                unit_ui_options=unit_ui_options,
            )

            rows_out.append({
                "item_id": item_id,
                "item_name": item_name,
                "stock_qty": stock_qty,
                "stock_unit_id": ui_to_unit_id.get(stock_unit_ui, ""),
                "order_qty": order_qty,
                "order_unit_id": ui_to_unit_id.get(order_unit_ui, ""),
                "unit_price": price_today,
            })

            st.markdown("---")

        note = st.text_area("備註（可空）", value="")
        submitted = st.form_submit_button("✅ 一次送出（寫入點貨+叫貨）", use_container_width=True)

    if not submitted:
        return

    valid = [x for x in rows_out if (x["stock_qty"] > 0) or (x["order_qty"] > 0)]
    if not valid:
        st.warning("你沒有填任何庫存/進貨數字（全部是 0）。")
        return

    # Create stocktake_id
    try:
        stocktake_id = get_next_id(repo, key="stocktakes", env=env, actor_user_id=actor_user_id)
    except Exception as e:
        st.error(f"建立 stocktake_id 失敗：{e}")
        return

    now = _now_ts()

    stocktake_row = {
        "stocktake_id": stocktake_id,
        "env": env,
        "store_id": store_id,
        "stocktake_date": str(record_date),
        "note": note,
        "created_at": now,
        "created_by": actor_user_id,
        "updated_at": "",
        "updated_by": "",
    }

    lines = []
    for x in valid:
        line_id = get_next_id(repo, key="stocktake_lines", env=env, actor_user_id=actor_user_id)
        lines.append({
            "stocktake_line_id": line_id,
            "env": env,
            "stocktake_id": stocktake_id,
            "store_id": store_id,
            "vendor_id": vendor_id,
            "item_id": x["item_id"],
            "item_name_snapshot": x["item_name"],
            "stock_qty": str(round(float(x["stock_qty"]), 1)),
            "stock_unit_id": x["stock_unit_id"],
            "order_qty": str(round(float(x["order_qty"]), 1)),
            "order_unit_id": x["order_unit_id"],
            "unit_price": str(x["unit_price"]),
            "amount": str(round(float(x["order_qty"]) * float(x["unit_price"]), 2)),
            "note": "",
            "created_at": now,
            "created_by": actor_user_id,
            "updated_at": "",
            "updated_by": "",
        })

    try:
        repo.append_row_dict("stocktakes", stocktake_row)
        repo.append_rows("stocktake_lines", lines)
        bust_cache()
        st.success(f"✅ 已送出成功：stocktake_id = {stocktake_id}（共 {len(lines)} 筆）")
    except Exception as e:
        st.error(f"寫入失敗（可能限流/欄位不匹配）：{e}")
        st.info("如果是限流：等 30~60 秒再試一次，或少量分批送出。")


# ============================================================
# Navigation
# ============================================================

def _resolve_nav_target_before_widget(default_page: str):
    target = st.session_state.pop("nav_target", None)
    if target:
        st.session_state["nav_page"] = target
    else:
        st.session_state.setdefault("nav_page", default_page)


# ============================================================
# Main
# ============================================================

def main():
    page_header()

    sheet_id, creds_path, env, audit_sheet = sidebar_system_config()
    actor_user_id, actor_role = sidebar_actor_selector()

    if not sheet_id:
        fail("Sheet ID 不能空白。")

    if "gcp" not in st.secrets:
        if not creds_path:
            fail("本機測試：Service Account JSON Path 不能空白。")
        if not Path(creds_path).exists():
            fail(f"找不到 service_account.json：{creds_path}")

    try:
        repo = get_repo_cached(sheet_id, creds_path if "gcp" not in st.secrets else None)
    except Exception as e:
        fail(f"Repo 初始化失敗：{e}")

    with st.sidebar:
        st.divider()
        st.subheader("📚 Navigation")

        is_admin = ROLE_RANK.get(actor_role, 0) >= ROLE_RANK["Admin"]

        pages = ["Stocktake / Order"] if is_admin else ["(No Access)"]

        _resolve_nav_target_before_widget(default_page=pages[0])
        page = st.radio("Page", options=pages, key="nav_page")

    if page == "Stocktake / Order":
        page_stocktake_order(repo, sheet_id=sheet_id, env=env, actor_user_id=actor_user_id)
    else:
        st.info("目前此角色沒有可用頁面。")


if __name__ == "__main__":
    st.set_page_config(page_title="ORIVIA OMS Admin UI", layout="wide")
    main()
