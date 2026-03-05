# ============================================================
# ORIVIA OMS Admin UI + 點貨/叫貨（同頁）— Stable + Cache + RBAC + Retry
# 單檔 app.py：可上 GitHub + Streamlit Cloud
#
# ✅ 已有：Vendors / Units / Items / Prices（Admin）
# ✅ 新增：點貨/叫貨（同頁）：選分店→選廠商→品項兩格（庫/進）→一次送出
# ✅ 強化：gspread 自動重試 + worksheet 物件快取（降低限流）
# ============================================================

from __future__ import annotations

from pathlib import Path
from datetime import timedelta, date
import time
import random

import streamlit as st
import pandas as pd
import gspread
from gspread.exceptions import APIError
from google.oauth2.service_account import Credentials


# ============================================================
# Basic helpers
# ============================================================

def fail(msg: str):
    st.error(msg)
    st.stop()


def page_header():
    st.title("ORIVIA OMS Admin UI")
    st.caption("BUILD: stable + cache + actor + rbac + retry")


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


def _safe_float(x, default=0.0) -> float:
    try:
        if x is None:
            return float(default)
        s = str(x).strip()
        if s == "":
            return float(default)
        return float(s)
    except Exception:
        return float(default)


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
# Retry (限流自動重試)
# ============================================================

def _is_retryable_api_error(e: Exception) -> bool:
    if isinstance(e, APIError):
        try:
            code = getattr(e, "response", None).status_code  # type: ignore
            if code in (429, 500, 502, 503, 504):
                return True
        except Exception:
            return True
        return True
    return False


def with_retry(fn, *, tries=5, base_sleep=0.6):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e
            if not _is_retryable_api_error(e):
                raise
            # exponential backoff + jitter
            sleep_s = base_sleep * (2 ** i) + random.random() * 0.2
            time.sleep(min(sleep_s, 6.0))
    raise last  # type: ignore


# ============================================================
# Repo (Google Sheets) + worksheet cache
# ============================================================

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
        self.sh = gc.open_by_key(sheet_id)
        self._ws_cache: dict[str, gspread.Worksheet] = {}

    def get_ws(self, table: str):
        if table in self._ws_cache:
            return self._ws_cache[table]
        ws = with_retry(lambda: self.sh.worksheet(table))
        self._ws_cache[table] = ws
        return ws

    def fetch_all_values(self, table: str) -> list[list[str]]:
        ws = self.get_ws(table)
        return with_retry(lambda: ws.get_all_values())

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
        with_retry(lambda: ws.append_row(out, value_input_option="USER_ENTERED"))

    def append_rows_dicts(self, table: str, rows: list[dict]):
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

        with_retry(lambda: ws.append_rows(out_rows, value_input_option="USER_ENTERED"))

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
        with_retry(lambda: ws.update(f"{start}:{end}", [row_values], value_input_option="USER_ENTERED"))

    def update_fields_by_row(self, table: str, row_index_1based: int, patch: dict):
        ws = self.get_ws(table)
        values = self.fetch_all_values(table)
        if not values:
            raise ValueError(f"Table '{table}' has no header row.")
        header = values[0]

        row_vals = with_retry(lambda: ws.row_values(row_index_1based))
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
# Cache layer (quota protection)
# ============================================================

@st.cache_resource(show_spinner=False)
def get_repo_cached(sheet_id: str, creds_path: str | None):
    return GoogleSheetsRepo(sheet_id=sheet_id, creds_path=creds_path)


@st.cache_data(show_spinner=False, ttl=120)
def cached_table_values(sheet_id: str, table: str, cache_bust: int) -> list[list[str]]:
    repo = get_repo_cached(sheet_id, None)
    return repo.fetch_all_values(table)


def read_table(repo: GoogleSheetsRepo, sheet_id: str, table: str) -> pd.DataFrame:
    bust = int(st.session_state.get("cache_bust", 0))
    values = cached_table_values(sheet_id, table, bust)
    if not values:
        return pd.DataFrame()
    header = values[0]
    rows = values[1:]
    return pd.DataFrame(rows, columns=header)


def read_table_with_rownum(repo: GoogleSheetsRepo, sheet_id: str, table: str) -> pd.DataFrame:
    bust = int(st.session_state.get("cache_bust", 0))
    values = cached_table_values(sheet_id, table, bust)
    if not values:
        return pd.DataFrame()
    header = values[0]
    rows = values[1:]
    df = pd.DataFrame(rows, columns=header)
    df["_row"] = list(range(2, 2 + len(rows)))
    return df


def bust_cache():
    st.session_state["cache_bust"] = int(st.session_state.get("cache_bust", 0)) + 1
    st.cache_data.clear()


# ============================================================
# Audit (best-effort)
# ============================================================

def try_append_audit(repo: GoogleSheetsRepo, audit_sheet: str, actor_user_id: str, action: str, entity: str, detail: str):
    try:
        ws = repo.get_ws(audit_sheet)
        values = repo.fetch_all_values(audit_sheet)
        if not values:
            return
        header = values[0]

        row = {c: "" for c in header}
        for k, v in {
            "ts": _now_ts(),
            "actor": actor_user_id,
            "action": action,
            "entity": entity,
            "detail": detail,
        }.items():
            if k in row:
                row[k] = v

        out = [row.get(c, "") for c in header]
        with_retry(lambda: ws.append_row(out, value_input_option="USER_ENTERED"))
    except Exception:
        return


# ============================================================
# ID Generator (from id_sequences)
# ============================================================

def _make_id(prefix: str, width: int, n: int) -> str:
    return f"{prefix}{str(n).zfill(int(width))}"


def get_next_id(repo: GoogleSheetsRepo, key: str, env: str, actor_user_id: str) -> str:
    ws = repo.get_ws("id_sequences")
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
    if "last_number" in updated:
        updated["last_number"] = str(next_value)
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
# Price lookup (prices table)
# ============================================================

def get_price_for_item_on(repo: GoogleSheetsRepo, sheet_id: str, item_id: str, target: date) -> tuple[float, str]:
    """
    回傳 (unit_price, price_id). 找不到則 (0.0, "")
    條件：
    - item_id 相符
    - effective_date <= target
    - end_date 空或 >= target
    - is_active 空或 TRUE
    - 取 effective_date 最新的一筆
    """
    df = read_table(repo, sheet_id, "prices")
    if df.empty:
        return 0.0, ""

    for col in ["item_id", "unit_price", "effective_date", "end_date", "is_active", "price_id"]:
        if col not in df.columns:
            return 0.0, ""

    tmp = df.copy()
    tmp["item_id"] = tmp["item_id"].astype(str).str.strip()
    tmp["__eff"] = tmp["effective_date"].apply(_parse_date)
    tmp["__end"] = tmp["end_date"].apply(_parse_date)
    tmp["__active"] = tmp["is_active"].apply(lambda x: (str(x).strip() == "" or str(x).strip().upper() == "TRUE"))

    t = target
    cand = tmp[
        (tmp["item_id"] == str(item_id).strip()) &
        (tmp["__active"]) &
        (tmp["__eff"].notna()) &
        (tmp["__eff"] <= t) &
        (tmp["__end"].isna() | (tmp["__end"] >= t))
    ].copy()

    if cand.empty:
        return 0.0, ""

    cand = cand.sort_values(by="__eff", ascending=True)
    r = cand.iloc[-1]
    price = _safe_float(r.get("unit_price", 0), 0.0)
    pid = str(r.get("price_id", "")).strip()
    return price, pid


# ============================================================
# Admin Pages (Vendors / Units / Items / Prices) — 保留你現況
# ============================================================
def apply_compact_mobile_row_style():
    st.markdown(
        """
        <style>
        /* 讓每列更緊湊 */
        .block-container { padding-top: 1.5rem; padding-left: 0.6rem; padding-right: 0.6rem; }

        /* 隱藏 number input 的 +/- stepper */
        div[data-testid="stNumberInputStepUp"],
        div[data-testid="stNumberInputStepDown"] { display: none !important; }
        input[type=number] { -moz-appearance: textfield !important; -webkit-appearance: none !important; margin: 0 !important; }

        /* 讓 columns 在手機也盡量不換行（Streamlit 會自己做 RWD，但這能改善很多） */
        [data-testid="stHorizontalBlock"] { gap: 0.5rem; flex-wrap: nowrap !important; align-items: center !important; }
        [data-testid="column"] { min-width: 0 !important; }

        /* 壓縮 dataframe/table padding（如果你後面也會顯示表格） */
        [data-testid="stDataFrame"] [role="gridcell"],
        [data-testid="stDataFrame"] [role="columnheader"] {
            padding: 4px 4px !important;
            font-size: 12px !important;
            line-height: 1.1 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_item_row(
    item_id: str,
    item_name: str,
    stock_unit_text: str,
    order_unit_text: str,
    price_today: float | None = None,
    prev_stock: float | None = None,
    suggest_qty: float | None = None,
):
    """
    一列 = 品項名稱（左）+ 庫/進（右兩格）
    回傳：stock_value, order_value
    """
    c_name, c_stock, c_order = st.columns([7, 2, 2])

    with c_name:
        st.markdown(f"**{item_name}**")
        meta_parts = []
        if stock_unit_text:
            meta_parts.append(f"庫單位：{stock_unit_text}")
        if order_unit_text:
            meta_parts.append(f"叫貨單位：{order_unit_text}")
        if price_today is not None:
            meta_parts.append(f"單價(當日)：{price_today:.2f}")
        if prev_stock is not None:
            meta_parts.append(f"前結：{prev_stock:.1f}")
        if suggest_qty is not None:
            meta_parts.append(f"💡建議：{suggest_qty:.1f}")

        if meta_parts:
            st.caption("｜".join(meta_parts))

        # 顯示 item_id（你原本有綠色 tag 的感覺）
        st.code(item_id, language=None)

    with c_stock:
        stock_v = st.number_input(
            "庫",
            min_value=0.0,
            step=0.1,
            value=0.0,
            key=f"stk__{item_id}",
            label_visibility="collapsed",
        )

    with c_order:
        order_v = st.number_input(
            "進",
            min_value=0.0,
            step=0.1,
            value=0.0,
            key=f"ord__{item_id}",
            label_visibility="collapsed",
        )

    return float(stock_v), float(order_v)

def page_units_create(repo: GoogleSheetsRepo, sheet_id: str, env: str, actor_user_id: str):
    require_role("Admin", role_of(actor_user_id))

    st.subheader("Admin / Units / Create")
    st.markdown("### 新增單位")

    unit_name = st.text_input("單位名稱 (unit_name)", value="").strip()
    is_active = st.checkbox("啟用 (is_active)", value=True)

    col1, col2 = st.columns([1, 2])
    with col1:
        submit = st.button("✅ 建立單位", use_container_width=True)
    with col2:
        st.caption("ID 由 id_sequences 自動產生，並寫回 next_value。")

    if not submit:
        return

    if not unit_name:
        st.warning("請輸入單位名稱")
        st.stop()

    units_df = read_table(repo, sheet_id, "units")
    if not units_df.empty and "unit_name" in units_df.columns:
        existed = units_df["unit_name"].astype(str).str.strip()
        if (existed == unit_name).any():
            st.error(f"已存在相同單位名稱：{unit_name}")
            st.stop()

    unit_id = get_next_id(repo, key="units", env=env, actor_user_id=actor_user_id)
    now = _now_ts()

    new_unit = {
        "unit_id": unit_id,
        "unit_name": unit_name,
        "is_active": _to_bool_str(is_active),
        "note": "",
        "created_at": now,
        "created_by": actor_user_id,
        "updated_at": "",
        "updated_by": "",
    }

    repo.append_row_dict("units", new_unit)
    bust_cache()

    st.success(f"✅ 建立成功：{unit_name}（{unit_id}）")
    st.json(new_unit)


def page_vendors_create(repo: GoogleSheetsRepo, sheet_id: str, env: str, actor_user_id: str):
    require_role("Admin", role_of(actor_user_id))

    st.subheader("Admin / Vendors / Create")
    st.markdown("### 新增廠商")

    vendor_name = st.text_input("廠商名稱 (vendor_name)", value="").strip()
    is_active = st.checkbox("啟用 (is_active)", value=True)

    col1, col2 = st.columns([1, 2])
    with col1:
        submit = st.button("✅ 建立廠商", use_container_width=True)
    with col2:
        st.caption("ID 由 id_sequences 自動產生，並寫回 next_value。")

    if not submit:
        return

    if not vendor_name:
        st.warning("請輸入廠商名稱")
        st.stop()

    vendor_id = get_next_id(repo, key="vendors", env=env, actor_user_id=actor_user_id)
    now = _now_ts()

    new_vendor = {
        "vendor_id": vendor_id,
        "brand_id": "",
        "vendor_name": vendor_name,
        "is_active": _to_bool_str(is_active),
        "audit": "",
        "note": "",
        "created_at": now,
        "created_by": actor_user_id,
        "updated_at": "",
        "updated_by": "",
    }

    repo.append_row_dict("vendors", new_vendor)
    bust_cache()

    st.success(f"✅ 建立成功：{vendor_name}（{vendor_id}）")
    st.json(new_vendor)


def page_items_create(repo: GoogleSheetsRepo, sheet_id: str, env: str, actor_user_id: str):
    require_role("Admin", role_of(actor_user_id))

    st.subheader("Admin / Items / Create")
    st.markdown("### 新增品項")

    vendors_df = read_table(repo, sheet_id, "vendors")
    if vendors_df.empty:
        st.warning("沒有 vendors，請先建立廠商")
        return

    if "is_active" in vendors_df.columns:
        vendors_df = vendors_df[vendors_df["is_active"].astype(str).str.upper() == "TRUE"]

    vendor_map = {
        f"{row.get('vendor_name','')} ({row.get('vendor_id','')})": row.get("vendor_id", "")
        for _, row in vendors_df.iterrows()
        if str(row.get("vendor_id", "")).strip()
    }
    if not vendor_map:
        st.warning("沒有可用的啟用廠商（vendors.is_active=TRUE）")
        return

    vendor_label = st.selectbox("選擇廠商", options=list(vendor_map.keys()))
    vendor_id = vendor_map[vendor_label]

    units_df = read_table(repo, sheet_id, "units")
    unit_map, unit_options = {}, []

    if not units_df.empty and "unit_id" in units_df.columns:
        if "is_active" in units_df.columns:
            units_df = units_df[units_df["is_active"].astype(str).str.upper() == "TRUE"]

        def _u_label(r):
            name = str(r.get("unit_name", "")).strip() if "unit_name" in units_df.columns else ""
            uid = str(r.get("unit_id", "")).strip()
            return f"{name} ({uid})" if name else uid

        unit_map = {_u_label(r): str(r.get("unit_id", "")).strip() for _, r in units_df.iterrows()}
        unit_options = list(unit_map.keys())

    col_u1, col_u2 = st.columns(2)
    with col_u1:
        stock_unit_label = st.selectbox("庫存單位 stock_unit", options=unit_options) if unit_options else st.text_input("庫存單位 stock_unit（先手輸入）")
    with col_u2:
        order_unit_label = st.selectbox("叫貨單位 order_unit", options=unit_options) if unit_options else st.text_input("叫貨單位 order_unit（先手輸入）")

    stock_unit = unit_map.get(stock_unit_label, stock_unit_label).strip() if isinstance(stock_unit_label, str) else ""
    order_unit = unit_map.get(order_unit_label, order_unit_label).strip() if isinstance(order_unit_label, str) else ""

    item_name = st.text_input("品項名稱（內部） item_name", value="").strip()
    item_name_zh = st.text_input("中文名稱 item_name_zh", value=item_name).strip()
    item_name_en = st.text_input("英文名稱 item_name_en（可空）", value="").strip()
    item_code = st.text_input("品項代碼 item_code（可空）", value="").strip()
    is_active = st.checkbox("啟用", value=True)

    submit = st.button("建立品項", use_container_width=True)
    if not submit:
        return

    if not item_name:
        st.warning("請輸入 item_name")
        return
    if not stock_unit or not order_unit:
        st.warning("請選擇（或填寫）庫存單位與叫貨單位")
        return

    item_id = get_next_id(repo, key="items", env=env, actor_user_id=actor_user_id)
    now = _now_ts()

    new_item = {
        "item_id": item_id,
        "brand_id": "",
        "vendor_id": vendor_id,
        "item_code": item_code,
        "item_name": item_name,
        "item_name_zh": item_name_zh,
        "item_name_en": item_name_en,
        "stock_unit": stock_unit,
        "order_unit": order_unit,
        "is_active": _to_bool_str(is_active),
        "audit": "",
        "note": "",
        "created_at": now,
        "created_by": actor_user_id,
        "updated_at": "",
        "updated_by": "",
    }

    repo.append_row_dict("items", new_item)
    bust_cache()

    st.success(f"✅ 建立成功：{item_name}（{item_id}）")
    st.json(new_item)


def page_prices_create(repo: GoogleSheetsRepo, sheet_id: str, env: str, actor_user_id: str, audit_sheet: str):
    require_role("Admin", role_of(actor_user_id))

    st.subheader("Admin / Prices / Create")
    st.markdown("### 新增價格（歷史價格）")

    items_df = read_table(repo, sheet_id, "items")
    if items_df.empty:
        st.warning("沒有 items，請先建立品項")
        return

    if "is_active" in items_df.columns:
        items_df = items_df[items_df["is_active"].astype(str).str.upper() == "TRUE"]

    def _item_label(r):
        name = ""
        if "item_name_zh" in items_df.columns and str(r.get("item_name_zh", "")).strip():
            name = str(r.get("item_name_zh", "")).strip()
        elif "item_name" in items_df.columns and str(r.get("item_name", "")).strip():
            name = str(r.get("item_name", "")).strip()
        iid = str(r.get("item_id", "")).strip()
        return f"{name} ({iid})" if name else iid

    item_map = {
        _item_label(r): str(r.get("item_id", "")).strip()
        for _, r in items_df.iterrows()
        if str(r.get("item_id", "")).strip()
    }
    if not item_map:
        st.warning("沒有可用品項（items.is_active=TRUE）")
        return

    item_label = st.selectbox("選擇品項", options=list(item_map.keys()))
    item_id = item_map[item_label]

    prices_df = read_table_with_rownum(repo, sheet_id, "prices")
    if prices_df.empty:
        st.info("prices 目前沒有資料，你將建立第一筆價格。")
    else:
        for col in ["item_id", "price_id", "unit_price", "effective_date", "end_date", "is_active"]:
            if col not in prices_df.columns:
                prices_df[col] = ""

    # 找現行價（end_date 空）
    current_row = None
    if not prices_df.empty:
        tmp = prices_df.copy()
        tmp["__eff"] = tmp["effective_date"].apply(_parse_date)
        tmp["__end"] = tmp["end_date"].apply(_parse_date)
        tmp["__active"] = tmp["is_active"].apply(lambda x: (str(x).strip() == "" or str(x).strip().upper() == "TRUE"))

        cur = tmp[
            (tmp["item_id"].astype(str) == str(item_id)) &
            (tmp["__active"]) &
            (tmp["__end"].isna())
        ].copy()

        if len(cur) > 0:
            cur = cur.sort_values(by="__eff", ascending=True)
            current_row = cur.iloc[-1].to_dict()

    if current_row:
        st.markdown("#### 目前現行價")
        st.write(
            f"- price_id：`{current_row.get('price_id','')}`\n"
            f"- unit_price：`{current_row.get('unit_price','')}`\n"
            f"- effective_date：`{current_row.get('effective_date','')}`\n"
            f"- end_date：`(空)`"
        )

    st.divider()
    st.markdown("#### 套用新現行價（自動封存舊價）")

    unit_price = st.number_input("單價 unit_price", min_value=0.0, step=1.0, format="%.2f")
    effective_date = st.date_input("生效日 effective_date")
    is_active = st.checkbox("啟用 (is_active)", value=True)

    do_apply = st.button("✅ 套用新現行價", use_container_width=True)
    if not do_apply:
        return

    if unit_price <= 0:
        st.warning("單價必須 > 0")
        return

    new_eff: date = effective_date
    now = _now_ts()

    # 封存舊價
    if current_row:
        old_eff = _parse_date(current_row.get("effective_date", ""))
        if old_eff and new_eff <= old_eff:
            st.error("⚠️ 新生效日必須晚於目前現行價的生效日。")
            st.stop()

        if old_eff:
            old_end: date = new_eff - timedelta(days=1)
            if old_end < old_eff:
                st.error("⚠️ 會造成舊價格區間不合法（end_date < effective_date）。")
                st.stop()

            repo.update_fields_by_row(
                "prices",
                int(current_row["_row"]),
                {
                    "end_date": str(old_end),
                    "updated_at": now,
                    "updated_by": actor_user_id,
                    "note": f"[CLOSE] close by new price effective_date={new_eff}",
                },
            )

    price_id = get_next_id(repo, key="prices", env=env, actor_user_id=actor_user_id)

    new_price = {
        "price_id": price_id,
        "brand_id": "",
        "vendor_id": "",
        "item_id": str(item_id),
        "unit_price": str(unit_price),
        "effective_date": str(new_eff),
        "end_date": "",
        "is_active": _to_bool_str(is_active),
        "audit": "",
        "note": "",
        "created_at": now,
        "created_by": actor_user_id,
        "updated_at": "",
        "updated_by": "",
    }

    # 補齊 prices 表頭欄位
    ws = repo.get_ws("prices")
    header = repo.fetch_all_values("prices")[0]
    for c in header:
        if c not in new_price:
            new_price[c] = ""

    repo.append_row_dict("prices", new_price)
    bust_cache()

    try_append_audit(
        repo=repo,
        audit_sheet=audit_sheet,
        actor_user_id=actor_user_id,
        action="PRICE_APPLY_NEW",
        entity=str(item_id),
        detail=f"new_price_id={price_id}, unit_price={unit_price}, effective_date={new_eff}",
    )

    st.success(f"✅ 已套用新現行價：{item_label} / {unit_price}（{price_id}）")
    st.rerun()


# ============================================================
# New: 點貨/叫貨（同頁）— 依你舊版 fill_items 呈現
# ============================================================

def page_stocktake_and_po(repo: GoogleSheetsRepo, sheet_id: str, env: str, actor_user_id: str, audit_sheet: str):
    # 這頁你可以視需求改成 StoreManager 也能用；目前先放寬：Admin 以上可用
    require_role("Admin", role_of(actor_user_id))

    st.subheader("點貨 / 叫貨（同頁）")
    st.caption("選分店 → 選廠商 → 每個品項輸入：庫存（stock_unit）與叫貨（order_unit）→ 一次送出")

    stores_df = read_table(repo, sheet_id, "stores")
    vendors_df = read_table(repo, sheet_id, "vendors")
    items_df = read_table(repo, sheet_id, "items")
    units_df = read_table(repo, sheet_id, "units")

    if stores_df.empty or "store_id" not in stores_df.columns:
        st.warning("stores 尚未有資料或缺少 store_id")
        return
    if vendors_df.empty or "vendor_id" not in vendors_df.columns:
        st.warning("vendors 尚未有資料或缺少 vendor_id")
        return
    if items_df.empty or "item_id" not in items_df.columns:
        st.warning("items 尚未有資料或缺少 item_id")
        return

    # active filter
    if "is_active" in stores_df.columns:
        stores_df = stores_df[stores_df["is_active"].astype(str).str.upper().isin(["TRUE", ""])]
    if "is_active" in vendors_df.columns:
        vendors_df = vendors_df[vendors_df["is_active"].astype(str).str.upper().isin(["TRUE", ""])]
    if "is_active" in items_df.columns:
        items_df = items_df[items_df["is_active"].astype(str).str.upper().isin(["TRUE", ""])]

    # unit name map
    unit_name_map = {}
    if not units_df.empty and "unit_id" in units_df.columns:
        for _, r in units_df.iterrows():
            uid = str(r.get("unit_id", "")).strip()
            nm = str(r.get("unit_name", "")).strip() if "unit_name" in units_df.columns else ""
            if uid:
                unit_name_map[uid] = nm or uid

    # store select
    def _store_label(r):
        sid = str(r.get("store_id", "")).strip()
        nm = str(r.get("store_name_zh", "")).strip() if "store_name_zh" in stores_df.columns else ""
        if not nm:
            nm = str(r.get("store_name", "")).strip() if "store_name" in stores_df.columns else ""
        return f"{nm} ({sid})" if nm else sid

    store_map = {_store_label(r): str(r.get("store_id", "")).strip() for _, r in stores_df.iterrows() if str(r.get("store_id","")).strip()}
    if not store_map:
        st.warning("stores 沒有可用資料（可能都 inactive）")
        return

    colA, colB, colC = st.columns([2, 2, 1])
    with colA:
        store_label = st.selectbox("分店", options=list(store_map.keys()))
        store_id = store_map[store_label]
    with colB:
        record_date = st.date_input("盤點/叫貨日期", value=date.today())
    with colC:
        status = st.selectbox("叫貨狀態", options=["DRAFT", "SUBMITTED"], index=1)

    # vendor select
    def _vendor_label(r):
        vid = str(r.get("vendor_id","")).strip()
        vn = str(r.get("vendor_name","")).strip()
        return f"{vn} ({vid})" if vn else vid

    vendor_map = {_vendor_label(r): str(r.get("vendor_id","")).strip() for _, r in vendors_df.iterrows() if str(r.get("vendor_id","")).strip()}
    if not vendor_map:
        st.warning("vendors 沒有可用資料（可能都 inactive）")
        return

    vendor_label = st.selectbox("廠商", options=list(vendor_map.keys()))
    vendor_id = vendor_map[vendor_label]

    # items filter by vendor_id
    if "vendor_id" not in items_df.columns:
        st.error("items 缺少 vendor_id 欄位")
        return

    v_items = items_df[items_df["vendor_id"].astype(str).str.strip() == str(vendor_id).strip()].copy()
    if v_items.empty:
        st.info("此廠商尚無 items")
        return

    # display name
    def _item_name(r):
        zh = str(r.get("item_name_zh","")).strip()
        nm = str(r.get("item_name","")).strip()
        return zh or nm or str(r.get("item_id","")).strip()

    st.divider()
    st.markdown("### 品項輸入（庫 / 進）")

    # header row
    h1, h2, h3 = st.columns([6, 2, 2])
    h1.markdown("**品項**")
    h2.markdown("**庫（stock）**")
    h3.markdown("**進（order）**")

    # input form
    with st.form("form_stock_po"):
        rows = []
        for _, r in v_items.iterrows():
            iid = str(r.get("item_id","")).strip()
            name = _item_name(r)
            stock_unit_id = str(r.get("stock_unit","")).strip()
            order_unit_id = str(r.get("order_unit","")).strip()
            stock_unit_name = unit_name_map.get(stock_unit_id, stock_unit_id or "-")
            order_unit_name = unit_name_map.get(order_unit_id, order_unit_id or "-")

            price, price_id = get_price_for_item_on(repo, sheet_id, iid, record_date)

            c1, c2, c3 = st.columns([6, 2, 2])
            with c1:
                st.markdown(f"**{name}**  \n`{iid}`")
                st.caption(f"庫單位：{stock_unit_name}｜叫貨單位：{order_unit_name}｜單價（當日）：{price:.2f}")

            with c2:
                stock_qty = st.number_input(
                    "庫",
                    min_value=0.0,
                    step=0.1,
                    format="%g",
                    value=None,
                    key=f"stk_{iid}",
                    label_visibility="collapsed",
                )
            with c3:
                order_qty = st.number_input(
                    "進",
                    min_value=0.0,
                    step=0.1,
                    format="%g",
                    value=None,
                    key=f"ord_{iid}",
                    label_visibility="collapsed",
                )

            rows.append({
                "item_id": iid,
                "item_name": name,
                "stock_qty": stock_qty,
                "order_qty": order_qty,
                "stock_unit_id": stock_unit_id,
                "order_unit_id": order_unit_id,
                "unit_price": price,
                "price_id": price_id,
            })

        note = st.text_input("備註（可空）", value="").strip()
        submit = st.form_submit_button("✅ 一次送出（寫入點貨+叫貨）", use_container_width=True)

    if not submit:
        return

    # Fail-fast 驗證：至少有一筆輸入
    any_input = any((r["stock_qty"] is not None) or (r["order_qty"] is not None and _safe_float(r["order_qty"]) > 0) for r in rows)
    if not any_input:
        st.warning("你沒有輸入任何數量（庫/進 都空）。")
        return

    # Fail-fast：叫貨有填 qty 的，必須找得到價格
    missing_price = []
    for r in rows:
        oq = r["order_qty"]
        if oq is not None and _safe_float(oq) > 0:
            if r["unit_price"] <= 0:
                missing_price.append(f"{r['item_name']} ({r['item_id']})")
    if missing_price:
        st.error("以下品項找不到有效價格（prices），已阻止送出：\n- " + "\n- ".join(missing_price))
        st.stop()

    now = _now_ts()

    # 建立 header（點貨 / 叫貨）— 只要有任何 stock_qty 就建立 stocktake；只要有任何 order_qty>0 就建立 PO
    has_stock = any(r["stock_qty"] is not None for r in rows)
    has_po = any((r["order_qty"] is not None and _safe_float(r["order_qty"]) > 0) for r in rows)

    stocktake_id = ""
    po_id = ""

    if has_stock:
        stocktake_id = get_next_id(repo, key="stocktakes", env=env, actor_user_id=actor_user_id)
        stocktake_header = {
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
        # 補齊表頭欄位
        hdr = repo.fetch_all_values("stocktakes")[0]
        for c in hdr:
            if c not in stocktake_header:
                stocktake_header[c] = ""
        repo.append_row_dict("stocktakes", stocktake_header)

    if has_po:
        po_id = get_next_id(repo, key="purchase_orders", env=env, actor_user_id=actor_user_id)
        po_header = {
            "po_id": po_id,
            "env": env,
            "store_id": store_id,
            "vendor_id": vendor_id,
            "order_date": str(record_date),
            "expected_date": "",
            "status": status,
            "note": note,
            "created_at": now,
            "created_by": actor_user_id,
            "updated_at": "",
            "updated_by": "",
        }
        hdr = repo.fetch_all_values("purchase_orders")[0]
        for c in hdr:
            if c not in po_header:
                po_header[c] = ""
        repo.append_row_dict("purchase_orders", po_header)

    # lines
    stock_lines: list[dict] = []
    po_lines: list[dict] = []

    for r in rows:
        iid = r["item_id"]

        if has_stock and r["stock_qty"] is not None:
            line_id = get_next_id(repo, key="stocktake_lines", env=env, actor_user_id=actor_user_id)
            stock_lines.append({
                "stocktake_line_id": line_id,
                "env": env,
                "stocktake_id": stocktake_id,
                "item_id": iid,
                "qty": str(_safe_float(r["stock_qty"], 0.0)),
                "unit_id": r["stock_unit_id"],
                "note": "",
                "created_at": now,
                "created_by": actor_user_id,
            })

        if has_po and r["order_qty"] is not None and _safe_float(r["order_qty"]) > 0:
            oq = _safe_float(r["order_qty"], 0.0)
            price = float(r["unit_price"])
            amt = round(oq * price, 4)

            line_id = get_next_id(repo, key="purchase_order_lines", env=env, actor_user_id=actor_user_id)
            po_lines.append({
                "po_line_id": line_id,
                "env": env,
                "po_id": po_id,
                "item_id": iid,
                "qty": str(oq),
                "unit_id": r["order_unit_id"],
                "unit_price": str(price),
                "amount": str(amt),
                "price_id": r["price_id"],
                "note": "",
                "created_at": now,
                "created_by": actor_user_id,
            })

    # 補齊 lines header 欄位（避免表頭多欄位時 append 失敗）
    if stock_lines:
        hdr = repo.fetch_all_values("stocktake_lines")[0]
        for row in stock_lines:
            for c in hdr:
                if c not in row:
                    row[c] = ""

    if po_lines:
        hdr = repo.fetch_all_values("purchase_order_lines")[0]
        for row in po_lines:
            for c in hdr:
                if c not in row:
                    row[c] = ""

    # 批次寫入 lines（減少 API 次數、降低限流）
    if stock_lines:
        repo.append_rows_dicts("stocktake_lines", stock_lines)
    if po_lines:
        repo.append_rows_dicts("purchase_order_lines", po_lines)

    # audit
    try_append_audit(repo, audit_sheet, actor_user_id, "STOCK_PO_SUBMIT", f"{store_id}/{vendor_id}", f"stocktake={stocktake_id}, po={po_id}")

    bust_cache()

    st.success("✅ 已成功寫入！")
    st.write(f"- stocktake_id：`{stocktake_id or '(未建立)'}`")
    st.write(f"- po_id：`{po_id or '(未建立)'}`")
    st.caption("若你想做『今日叫貨明細→LINE』，下一步我們直接用 purchase_order_lines 產出即可。")


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

        if is_admin:
            pages = [
                "點貨/叫貨（同頁）",
                "Vendors / Create",
                "Units / Create",
                "Items / Create",
                "Prices / Create",
            ]
        else:
            pages = ["(No Access)"]

        # 只靠 session_state，不要用 index + 又改 session_state，避免你之前那個黃字
        if "nav_page" not in st.session_state or st.session_state["nav_page"] not in pages:
            st.session_state["nav_page"] = pages[0]
        page = st.radio("Page", options=pages, key="nav_page")

    if page == "點貨/叫貨（同頁）":
        page_stocktake_and_po(repo, sheet_id=sheet_id, env=env, actor_user_id=actor_user_id, audit_sheet=audit_sheet)

    elif page == "Vendors / Create":
        page_vendors_create(repo, sheet_id=sheet_id, env=env, actor_user_id=actor_user_id)

    elif page == "Units / Create":
        page_units_create(repo, sheet_id=sheet_id, env=env, actor_user_id=actor_user_id)

    elif page == "Items / Create":
        page_items_create(repo, sheet_id=sheet_id, env=env, actor_user_id=actor_user_id)

    elif page == "Prices / Create":
        page_prices_create(repo, sheet_id=sheet_id, env=env, actor_user_id=actor_user_id, audit_sheet=audit_sheet)

    else:
        st.info("目前此角色沒有可用頁面。")


if __name__ == "__main__":
    st.set_page_config(page_title="ORIVIA OMS Admin UI", layout="wide")
    main()

