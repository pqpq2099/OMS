# ============================================================
# ORIVIA OMS Admin UI
# Stable + Cache + Actor Selector + RBAC
# + Purchase Orders / Create
# ============================================================

from __future__ import annotations

from pathlib import Path
from datetime import timedelta, date
import time
import random
from collections import deque

import streamlit as st
import pandas as pd
import gspread
from gspread.exceptions import APIError
from google.oauth2.service_account import Credentials

from oms_engine import convert_to_base

st.set_page_config(page_title="ORIVIA OMS Admin UI", layout="wide")

# ============================================================
# Basic helpers
# ============================================================

def fail(msg: str):
    st.error(msg)
    st.stop()


def page_header():
    st.title("ORIVIA OMS Admin UI")
    st.caption("BUILD: stable + cache + actor + rbac + purchase orders")


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


# ============================================================
# Actor + Role
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
# Global rate limiter
# ============================================================

class RateLimiter:
    def __init__(self, rate: int = 4, per: float = 1.0):
        self.rate = int(rate)
        self.per = float(per)
        self._q = deque()

    def acquire(self):
        now = time.monotonic()

        while self._q and (now - self._q[0]) >= self.per:
            self._q.popleft()

        if len(self._q) < self.rate:
            self._q.append(now)
            return

        wait = self.per - (now - self._q[0])
        if wait > 0:
            time.sleep(wait)

        now2 = time.monotonic()
        while self._q and (now2 - self._q[0]) >= self.per:
            self._q.popleft()
        self._q.append(now2)


@st.cache_resource(show_spinner=False)
def get_rate_limiter_b2():
    return RateLimiter(rate=4, per=1.0)


def _is_retryable_api_error(e: Exception) -> bool:
    if isinstance(e, APIError):
        try:
            code = int(getattr(e.response, "status_code", 0) or 0)
        except Exception:
            code = 0

        if code == 429 or (500 <= code <= 599):
            return True

        try:
            payload = getattr(e, "response", None)
            if payload is not None and hasattr(payload, "json"):
                j = payload.json()
                c = int(j.get("error", {}).get("code", 0))
                if c == 429 or (500 <= c <= 599):
                    return True
        except Exception:
            pass

        return False

    return False


def _with_retry(fn, *, tries: int = 6, base_sleep: float = 0.6):
    limiter = get_rate_limiter_b2()
    last_err = None

    for i in range(tries):
        try:
            limiter.acquire()
            return fn()
        except Exception as e:
            last_err = e
            if not _is_retryable_api_error(e):
                raise

            sleep = base_sleep * (2 ** i)
            sleep = min(sleep, 8.0)
            sleep = sleep * (0.85 + random.random() * 0.3)
            time.sleep(sleep)

    raise last_err


# ============================================================
# Repo (Google Sheets)
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

        gc = _with_retry(lambda: gspread.authorize(creds))
        self.sh = _with_retry(lambda: gc.open_by_key(sheet_id))
        self._ws_cache: dict[str, gspread.Worksheet] = {}

    def get_ws(self, table: str) -> gspread.Worksheet:
        if table in self._ws_cache:
            return self._ws_cache[table]
        ws = _with_retry(lambda: self.sh.worksheet(table))
        self._ws_cache[table] = ws
        return ws

    def fetch_all_values(self, table: str) -> list[list[str]]:
        ws = self.get_ws(table)
        return _with_retry(lambda: ws.get_all_values())

    def fetch_header(self, table: str) -> list[str]:
        ws = self.get_ws(table)
        return _with_retry(lambda: ws.row_values(1))

    def append_row_by_header(self, table: str, header: list[str], row: dict):
        ws = self.get_ws(table)

        missing = [c for c in header if c not in row]
        if missing:
            raise ValueError(f"Append '{table}' missing fields: {missing}")

        out = [row.get(c, "") for c in header]
        _with_retry(lambda: ws.append_row(out, value_input_option="USER_ENTERED"))

    def update_row_by_header(self, table: str, header: list[str], row_index_1based: int, new_row: dict):
        ws = self.get_ws(table)

        missing = [c for c in header if c not in new_row]
        if missing:
            raise ValueError(f"Update '{table}' missing fields: {missing}")

        row_values = [new_row.get(c, "") for c in header]
        start = gspread.utils.rowcol_to_a1(row_index_1based, 1)
        end = gspread.utils.rowcol_to_a1(row_index_1based, len(header))
        _with_retry(lambda: ws.update(f"{start}:{end}", [row_values], value_input_option="USER_ENTERED"))

    def update_fields_by_row(self, table: str, header: list[str], row_index_1based: int, patch: dict):
        ws = self.get_ws(table)
        row_vals = _with_retry(lambda: ws.row_values(row_index_1based))
        row_vals = row_vals + [""] * (len(header) - len(row_vals))
        cur = dict(zip(header, row_vals))

        for k, v in patch.items():
            if k in header:
                cur[k] = "" if v is None else str(v)

        for c in header:
            if c not in cur:
                cur[c] = ""

        self.update_row_by_header(table, header, row_index_1based, cur)


# ============================================================
# Cache layer
# ============================================================

@st.cache_resource(show_spinner=False)
def get_repo_cached(sheet_id: str, creds_path: str | None):
    return GoogleSheetsRepo(sheet_id=sheet_id, creds_path=creds_path)


@st.cache_data(show_spinner=False, ttl=600)
def cached_header(sheet_id: str, creds_path: str, table: str) -> list[str]:
    repo = get_repo_cached(sheet_id, None if not creds_path else creds_path)
    return repo.fetch_header(table)


@st.cache_data(show_spinner=False, ttl=120)
def cached_table_values(sheet_id: str, creds_path: str, table: str, cache_bust: int) -> list[list[str]]:
    repo = get_repo_cached(sheet_id, None if not creds_path else creds_path)
    return repo.fetch_all_values(table)


def bust_cache():
    st.session_state["cache_bust"] = int(st.session_state.get("cache_bust", 0)) + 1
    st.cache_data.clear()


def get_header(repo: GoogleSheetsRepo, sheet_id: str, creds_path: str, table: str) -> list[str]:
    h = cached_header(sheet_id, creds_path, table)
    if not h:
        raise ValueError(f"Table '{table}' has no header row.")
    return h


def read_table(repo: GoogleSheetsRepo, sheet_id: str, creds_path: str, table: str) -> pd.DataFrame:
    bust = int(st.session_state.get("cache_bust", 0))
    values = cached_table_values(sheet_id, creds_path, table, bust)
    if not values:
        return pd.DataFrame()
    header = values[0]
    rows = values[1:]
    return pd.DataFrame(rows, columns=header)


def read_table_with_rownum(repo: GoogleSheetsRepo, sheet_id: str, creds_path: str, table: str) -> pd.DataFrame:
    bust = int(st.session_state.get("cache_bust", 0))
    values = cached_table_values(sheet_id, creds_path, table, bust)
    if not values:
        return pd.DataFrame()
    header = values[0]
    rows = values[1:]
    df = pd.DataFrame(rows, columns=header)
    df["_row"] = list(range(2, 2 + len(rows)))
    return df


# ============================================================
# Audit
# ============================================================

def try_append_audit(
    repo: GoogleSheetsRepo,
    sheet_id: str,
    creds_path: str,
    audit_sheet: str,
    env: str,
    actor_user_id: str,
    action: str,
    table: str,
    entity_id: str,
    note: str,
    before_json: str = "",
    after_json: str = "",
):
    try:
        header = get_header(repo, sheet_id, creds_path, audit_sheet)
        row = {c: "" for c in header}

        mapping_v2 = {
            "ts": _now_ts(),
            "env": env,
            "action": action,
            "table": table,
            "entity_id": entity_id,
            "actor_user_id": actor_user_id,
            "before_json": before_json,
            "after_json": after_json,
            "note": note,
        }

        mapping_v1 = {
            "ts": _now_ts(),
            "actor": actor_user_id,
            "action": action,
            "entity": entity_id,
            "detail": note,
        }

        used = mapping_v2 if ("actor_user_id" in row or "entity_id" in row or "before_json" in row) else mapping_v1

        for k, v in used.items():
            if k in row:
                row[k] = v

        repo.append_row_by_header(audit_sheet, header, row)
        bust_cache()
    except Exception:
        return


# ============================================================
# ID Generator
# ============================================================

def _make_id(prefix: str, width: int, n: int) -> str:
    return f"{prefix}{str(n).zfill(int(width))}"


def get_next_id(repo: GoogleSheetsRepo, sheet_id: str, creds_path: str, key: str, env: str, actor_user_id: str) -> str:
    table = "id_sequences"
    values = repo.fetch_all_values(table)
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

    repo.update_row_by_header(table, header, sheet_row_index, updated)
    bust_cache()
    return new_id


# ============================================================
# Pages
# ============================================================

def page_vendors_create(repo: GoogleSheetsRepo, sheet_id: str, creds_path: str, env: str, actor_user_id: str):
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

    header = get_header(repo, sheet_id, creds_path, "vendors")
    vendor_id = get_next_id(repo, sheet_id, creds_path, key="vendors", env=env, actor_user_id=actor_user_id)
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

    for c in header:
        if c not in new_vendor:
            new_vendor[c] = ""

    repo.append_row_by_header("vendors", header, new_vendor)
    bust_cache()

    st.success(f"✅ 建立成功：{vendor_name}（{vendor_id}）")
    st.json(new_vendor)


def page_units_create(repo: GoogleSheetsRepo, sheet_id: str, creds_path: str, env: str, actor_user_id: str):
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

    units_df = read_table(repo, sheet_id, creds_path, "units")
    if not units_df.empty and "unit_name" in units_df.columns:
        existed = units_df["unit_name"].astype(str).str.strip()
        if (existed == unit_name).any():
            st.error(f"已存在相同單位名稱：{unit_name}")
            st.stop()

    header = get_header(repo, sheet_id, creds_path, "units")
    unit_id = get_next_id(repo, sheet_id, creds_path, key="units", env=env, actor_user_id=actor_user_id)
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

    for c in header:
        if c not in new_unit:
            new_unit[c] = ""

    repo.append_row_by_header("units", header, new_unit)
    bust_cache()

    st.success(f"✅ 建立成功：{unit_name}（{unit_id}）")
    st.json(new_unit)


def page_items_create(repo: GoogleSheetsRepo, sheet_id: str, creds_path: str, env: str, actor_user_id: str):
    require_role("Admin", role_of(actor_user_id))

    st.subheader("Admin / Items / Create")
    st.markdown("### 新增品項")

    vendors_df = read_table(repo, sheet_id, creds_path, "vendors")
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

    units_df = read_table(repo, sheet_id, creds_path, "units")
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
        stock_unit_label = st.selectbox("庫存單位 default_stock_unit", options=unit_options) if unit_options else st.text_input("庫存單位 default_stock_unit")
    with col_u2:
        order_unit_label = st.selectbox("叫貨單位 default_order_unit", options=unit_options) if unit_options else st.text_input("叫貨單位 default_order_unit")

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

    header = get_header(repo, sheet_id, creds_path, "items")
    item_id = get_next_id(repo, sheet_id, creds_path, key="items", env=env, actor_user_id=actor_user_id)
    now = _now_ts()

    # base_unit 先預設等於 default_stock_unit，之後你可再調整
    new_item = {
        "item_id": item_id,
        "brand_id": "",
        "vendor_id": vendor_id,
        "item_code": item_code,
        "item_name": item_name,
        "item_name_zh": item_name_zh,
        "item_name_en": item_name_en,
        "base_unit": stock_unit,
        "default_stock_unit": stock_unit,
        "default_order_unit": order_unit,
        "orderable_units": order_unit,
        "is_active": _to_bool_str(is_active),
        "audit": "",
        "note": "",
        "created_at": now,
        "created_by": actor_user_id,
        "updated_at": "",
        "updated_by": "",
    }

    for c in header:
        if c not in new_item:
            new_item[c] = ""

    repo.append_row_by_header("items", header, new_item)
    bust_cache()

    st.success(f"✅ 建立成功：{item_name}（{item_id}）")
    st.json(new_item)


def page_items_list(repo: GoogleSheetsRepo, sheet_id: str, creds_path: str, actor_user_id: str):
    require_role("Admin", role_of(actor_user_id))

    st.subheader("Admin / Items / List")

    df = read_table(repo, sheet_id, creds_path, "items")
    if df.empty:
        st.warning("items table 沒有資料")
        return
    if "item_id" not in df.columns:
        st.error("items table 缺少 item_id 欄位")
        return

    st.dataframe(df, use_container_width=True)

    st.divider()
    st.markdown("### 🔎 選取一筆 → 進入 Edit")

    pick = st.selectbox(
        "item_id",
        options=df["item_id"].astype(str).tolist(),
        index=0,
        key="pick_item_id",
    )
    st.write("你選到：", pick)

    if st.button("✏️ 進入 Edit", use_container_width=True):
        st.session_state["edit_item_id"] = pick
        st.session_state["nav_target"] = "Items / Edit"
        st.rerun()


def page_items_edit(repo: GoogleSheetsRepo, sheet_id: str, creds_path: str, actor_user_id: str):
    require_role("Admin", role_of(actor_user_id))

    st.subheader("Admin / Items / Edit")

    item_id = st.session_state.get("edit_item_id")
    if not item_id:
        st.info("請先到 Items / List 選一筆，再進 Edit。")
        return

    df = read_table(repo, sheet_id, creds_path, "items")
    if df.empty:
        st.warning("items table 沒資料")
        return

    row = df[df["item_id"].astype(str) == str(item_id)]
    if row.empty:
        st.error(f"找不到 item_id：{item_id}")
        return

    rec = row.iloc[0].to_dict()
    st.success(f"目前編輯：{item_id}")
    st.json(rec)


def page_prices_create(repo: GoogleSheetsRepo, sheet_id: str, creds_path: str, env: str, actor_user_id: str, audit_sheet: str):
    require_role("Admin", role_of(actor_user_id))

    st.subheader("Admin / Prices / Create")
    st.markdown("### 新增價格（歷史價格）")

    items_df = read_table(repo, sheet_id, creds_path, "items")
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

    prices_df = read_table_with_rownum(repo, sheet_id, creds_path, "prices")
    if prices_df.empty:
        st.info("prices 目前沒有資料，你將建立第一筆價格。")
    else:
        for col in ["item_id", "price_id", "unit_price", "effective_date", "end_date", "is_active"]:
            if col not in prices_df.columns:
                prices_df[col] = ""

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

        cur_eff = _parse_date(current_row.get("effective_date", ""))
        prev_row = None

        if cur_eff and not prices_df.empty:
            tmp2 = prices_df.copy()
            tmp2["__eff"] = tmp2["effective_date"].apply(_parse_date)
            tmp2["__end"] = tmp2["end_date"].apply(_parse_date)
            tmp2["__active"] = tmp2["is_active"].apply(lambda x: (str(x).strip() == "" or str(x).strip().upper() == "TRUE"))

            target_end = cur_eff - timedelta(days=1)
            prev = tmp2[
                (tmp2["item_id"].astype(str) == str(item_id)) &
                (tmp2["__active"]) &
                (tmp2["__end"] == target_end)
            ].copy()

            if len(prev) > 0:
                prev = prev.sort_values(by="__eff", ascending=True)
                prev_row = prev.iloc[-1].to_dict()

        col_rb1, col_rb2 = st.columns([1, 2])
        with col_rb1:
            do_rb = st.button("⏪ 撤回最新一次換價", use_container_width=True)
        with col_rb2:
            st.caption("只撤回『最新現行價』，並把上一筆價格恢復成現行價（end_date 清空）。")

        if do_rb:
            if not cur_eff:
                st.error("現行價 effective_date 解析失敗，無法撤回。")
                st.stop()
            if not prev_row:
                st.error("找不到上一筆可恢復的價格（需要上一筆 end_date = 現行價生效日前一天）。")
                st.stop()

            now = _now_ts()
            prices_header = get_header(repo, sheet_id, creds_path, "prices")

            repo.update_fields_by_row(
                "prices",
                prices_header,
                int(current_row["_row"]),
                {
                    "is_active": "FALSE",
                    "updated_at": now,
                    "updated_by": actor_user_id,
                    "note": f"[ROLLBACK] void current price {current_row.get('price_id','')}",
                },
            )

            repo.update_fields_by_row(
                "prices",
                prices_header,
                int(prev_row["_row"]),
                {
                    "end_date": "",
                    "updated_at": now,
                    "updated_by": actor_user_id,
                    "note": f"[ROLLBACK] restore as current (from {current_row.get('price_id','')})",
                },
            )

            try_append_audit(
                repo=repo,
                sheet_id=sheet_id,
                creds_path=creds_path,
                audit_sheet=audit_sheet,
                env=env,
                actor_user_id=actor_user_id,
                action="PRICE_ROLLBACK",
                table="prices",
                entity_id=str(item_id),
                note=f"void={current_row.get('price_id','')}, restore={prev_row.get('price_id','')}",
            )

            bust_cache()
            st.success("✅ 已撤回最新一次換價：新價已作廢，上一筆已恢復為現行價。")
            st.rerun()

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
    prices_header = get_header(repo, sheet_id, creds_path, "prices")

    if current_row:
        old_eff = _parse_date(current_row.get("effective_date", ""))
        if not old_eff:
            st.error("現行價 effective_date 解析失敗，無法換價。")
            st.stop()

        if new_eff <= old_eff:
            st.error("⚠️ 新生效日必須晚於目前現行價的生效日。")
            st.stop()

        old_end: date = new_eff - timedelta(days=1)
        if old_end < old_eff:
            st.error("⚠️ 會造成舊價格區間不合法（end_date < effective_date）。請調整新生效日。")
            st.stop()

        repo.update_fields_by_row(
            "prices",
            prices_header,
            int(current_row["_row"]),
            {
                "end_date": str(old_end),
                "updated_at": now,
                "updated_by": actor_user_id,
                "note": f"[CLOSE] close by new price effective_date={new_eff}",
            },
        )

    price_id = get_next_id(repo, sheet_id, creds_path, key="prices", env=env, actor_user_id=actor_user_id)

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

    for c in prices_header:
        if c not in new_price:
            new_price[c] = ""

    repo.append_row_by_header("prices", prices_header, new_price)
    bust_cache()

    try_append_audit(
        repo=repo,
        sheet_id=sheet_id,
        creds_path=creds_path,
        audit_sheet=audit_sheet,
        env=env,
        actor_user_id=actor_user_id,
        action="PRICE_APPLY_NEW",
        table="prices",
        entity_id=str(item_id),
        note=f"new_price_id={price_id}, unit_price={unit_price}, effective_date={new_eff}",
    )

    st.success(f"✅ 已套用新現行價：{item_label} / {unit_price}（{price_id}）")
    st.rerun()


def page_purchase_orders_create(
    repo: GoogleSheetsRepo,
    sheet_id: str,
    creds_path: str,
    env: str,
    actor_user_id: str,
    audit_sheet: str,
):
    require_role("Admin", role_of(actor_user_id))

    st.subheader("Admin / Purchase Orders / Create")
    st.markdown("### 新增叫貨單")

    items_df = read_table(repo, sheet_id, creds_path, "items")
    conv_df = read_table(repo, sheet_id, creds_path, "unit_conversions")
    prices_df = read_table(repo, sheet_id, creds_path, "prices")

    if items_df.empty:
        st.warning("items 沒有資料，請先建立品項")
        return

    if "is_active" in items_df.columns:
        items_df = items_df[items_df["is_active"].astype(str).str.upper() == "TRUE"]

    if items_df.empty:
        st.warning("沒有啟用中的品項")
        return

    def _item_label(r):
        name = str(r.get("item_name_zh", "")).strip()
        if not name:
            name = str(r.get("item_name", "")).strip()
        iid = str(r.get("item_id", "")).strip()
        return f"{name} ({iid})" if name else iid

    item_map = {
        _item_label(r): str(r.get("item_id", "")).strip()
        for _, r in items_df.iterrows()
        if str(r.get("item_id", "")).strip()
    }

    item_label = st.selectbox("品項", options=list(item_map.keys()))
    item_id = item_map[item_label]

    item_row = items_df[items_df["item_id"].astype(str) == str(item_id)]
    if item_row.empty:
        st.error("找不到品項資料")
        return

    item_rec = item_row.iloc[0].to_dict()

    default_order_unit = str(item_rec.get("default_order_unit", "")).strip()
    orderable_units_raw = str(item_rec.get("orderable_units", "")).strip()

    order_unit_options = []
    if orderable_units_raw:
        order_unit_options = [u.strip() for u in orderable_units_raw.split(",") if u.strip()]

    if default_order_unit and default_order_unit not in order_unit_options:
        order_unit_options.insert(0, default_order_unit)

    if not order_unit_options and default_order_unit:
        order_unit_options = [default_order_unit]

    if not order_unit_options:
        st.warning("此品項沒有 default_order_unit / orderable_units，請先補主檔")
        return

    col1, col2, col3 = st.columns([2, 2, 2])

    with col1:
        order_date = st.date_input("叫貨日期", value=date.today())

    with col2:
        order_qty = st.number_input("叫貨數量", min_value=0.0, step=1.0, format="%.1f")

    with col3:
        order_unit = st.selectbox("叫貨單位", options=order_unit_options)

    note = st.text_input("備註", value="").strip()

    preview_ok = False
    base_qty = None
    base_unit = None

    if order_qty > 0:
        try:
            base_qty, base_unit = convert_to_base(
                item_id=item_id,
                qty=order_qty,
                from_unit=order_unit,
                items_df=items_df,
                conversions_df=conv_df,
                as_of_date=order_date,
            )
            preview_ok = True
            st.success(f"換算結果：{order_qty} {order_unit} → {base_qty:.3f} {base_unit}")
        except Exception as e:
            st.error(f"單位換算失敗：{e}")

    unit_price = 0.0

    if not prices_df.empty and "item_id" in prices_df.columns:
        tmp = prices_df.copy()

        for col in ["effective_date", "end_date", "unit_price", "is_active"]:
            if col not in tmp.columns:
                tmp[col] = ""

        tmp = tmp[tmp["item_id"].astype(str) == str(item_id)].copy()

        if not tmp.empty:
            tmp["__eff"] = tmp["effective_date"].apply(_parse_date)
            tmp["__end"] = tmp["end_date"].apply(_parse_date)
            tmp["__active"] = tmp["is_active"].apply(
                lambda x: (str(x).strip() == "" or str(x).strip().upper() == "TRUE")
            )

            tmp = tmp[tmp["__active"]]

            tmp = tmp[
                (tmp["__eff"].isna() | (tmp["__eff"] <= order_date)) &
                (tmp["__end"].isna() | (tmp["__end"] >= order_date))
            ].copy()

            if not tmp.empty:
                tmp = tmp.sort_values(by="__eff", ascending=True)
                hit = tmp.iloc[-1].to_dict()
                try:
                    unit_price = float(hit.get("unit_price", 0) or 0)
                except Exception:
                    unit_price = 0.0

    line_amount = float(order_qty) * float(unit_price)
    st.caption(f"參考單價：{unit_price:.2f} ／ 小計：{line_amount:.2f}")

    submit = st.button("✅ 建立叫貨單", use_container_width=True)

    if not submit:
        return

    if order_qty <= 0:
        st.warning("叫貨數量必須大於 0")
        return

    if not preview_ok:
        st.warning("單位換算未成功，無法建立叫貨單")
        return

    po_header = get_header(repo, sheet_id, creds_path, "purchase_orders")
    pol_header = get_header(repo, sheet_id, creds_path, "purchase_order_lines")

    po_id = get_next_id(repo, sheet_id, creds_path, key="purchase_orders", env=env, actor_user_id=actor_user_id)
    po_line_id = get_next_id(repo, sheet_id, creds_path, key="purchase_order_lines", env=env, actor_user_id=actor_user_id)

    now = _now_ts()

    po_row = {c: "" for c in po_header}
    defaults_po = {
        "po_id": po_id,
        "brand_id": "",
        "store_id": "",
        "vendor_id": str(item_rec.get("vendor_id", "")).strip(),
        "order_date": str(order_date),
        "status": "draft",
        "note": note,
        "created_at": now,
        "created_by": actor_user_id,
        "updated_at": "",
        "updated_by": "",
    }
    for k, v in defaults_po.items():
        if k in po_row:
            po_row[k] = v

    repo.append_row_by_header("purchase_orders", po_header, po_row)

    pol_row = {c: "" for c in pol_header}
    defaults_pol = {
        "po_line_id": po_line_id,
        "po_id": po_id,
        "item_id": item_id,
        "qty": str(order_qty),
        "order_qty": str(order_qty),
        "unit_id": order_unit,
        "order_unit": order_unit,
        "base_qty": str(base_qty),
        "base_unit": str(base_unit),
        "unit_price": str(unit_price),
        "amount": str(line_amount),
        "line_amount": str(line_amount),
        "note": note,
        "created_at": now,
        "created_by": actor_user_id,
        "updated_at": "",
        "updated_by": "",
    }
    for k, v in defaults_pol.items():
        if k in pol_row:
            pol_row[k] = v

    repo.append_row_by_header("purchase_order_lines", pol_header, pol_row)
    bust_cache()

    try_append_audit(
        repo=repo,
        sheet_id=sheet_id,
        creds_path=creds_path,
        audit_sheet=audit_sheet,
        env=env,
        actor_user_id=actor_user_id,
        action="CREATE_PURCHASE_ORDER",
        table="purchase_orders",
        entity_id=po_id,
        note=f"item_id={item_id}, qty={order_qty}, unit={order_unit}, base_qty={base_qty}, base_unit={base_unit}",
    )

    st.success(f"✅ 建立成功：{po_id}")
    st.json({
        "po_id": po_id,
        "po_line_id": po_line_id,
        "item_id": item_id,
        "qty": order_qty,
        "unit": order_unit,
        "base_qty": base_qty,
        "base_unit": base_unit,
        "unit_price": unit_price,
        "amount": line_amount,
    })


# ============================================================
# Main
# ============================================================

def main():
    page_header()

    sheet_id, creds_path, env, audit_sheet = sidebar_system_config()
    actor_user_id, actor_role = sidebar_actor_selector()

    if not sheet_id:
        fail("Sheet ID 不能空白。")

    cp = "" if "gcp" in st.secrets else creds_path

    if "gcp" not in st.secrets:
        if not creds_path:
            fail("本機測試：Service Account JSON Path 不能空白。")
        if not Path(creds_path).exists():
            fail(f"找不到 service_account.json：{creds_path}")

    try:
        repo = get_repo_cached(sheet_id, None if "gcp" in st.secrets else creds_path)
    except Exception as e:
        fail(f"Repo 初始化失敗：{e}")

    with st.sidebar:
        st.divider()
        st.subheader("📚 Navigation")

        is_admin = ROLE_RANK.get(actor_role, 0) >= ROLE_RANK["Admin"]
        if is_admin:
            pages = [
                "Vendors / Create",
                "Units / Create",
                "Items / Create",
                "Items / List",
                "Items / Edit",
                "Prices / Create",
                "Purchase Orders / Create",
            ]
        else:
            pages = ["(No Access)"]

        if st.session_state.get("nav_target") in pages:
            st.session_state["nav_page"] = st.session_state["nav_target"]
            st.session_state["nav_target"] = None

        st.session_state.setdefault("nav_page", pages[0])

        page = st.radio("Page", options=pages, key="nav_page", index=pages.index(st.session_state["nav_page"]))

    if page == "Vendors / Create":
        page_vendors_create(repo, sheet_id=sheet_id, creds_path=cp, env=env, actor_user_id=actor_user_id)

    elif page == "Units / Create":
        page_units_create(repo, sheet_id=sheet_id, creds_path=cp, env=env, actor_user_id=actor_user_id)

    elif page == "Items / Create":
        page_items_create(repo, sheet_id=sheet_id, creds_path=cp, env=env, actor_user_id=actor_user_id)

    elif page == "Items / List":
        page_items_list(repo, sheet_id=sheet_id, creds_path=cp, actor_user_id=actor_user_id)

    elif page == "Items / Edit":
        page_items_edit(repo, sheet_id=sheet_id, creds_path=cp, actor_user_id=actor_user_id)

    elif page == "Prices / Create":
        page_prices_create(
            repo,
            sheet_id=sheet_id,
            creds_path=cp,
            env=env,
            actor_user_id=actor_user_id,
            audit_sheet=audit_sheet,
        )

    elif page == "Purchase Orders / Create":
        page_purchase_orders_create(
            repo,
            sheet_id=sheet_id,
            creds_path=cp,
            env=env,
            actor_user_id=actor_user_id,
            audit_sheet=audit_sheet,
        )

    else:
        st.info("目前此角色沒有可用頁面。")


if __name__ == "__main__":
    main()
