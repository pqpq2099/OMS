# ============================================================
# ORIVIA OMS Admin UI + Stocktake/Order (Single-file app.py)
# BUILD: stable + cache + actor + rbac + mobile-compact rows
# ============================================================

from __future__ import annotations

from pathlib import Path
from datetime import date, timedelta
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
    """
    label like: '公斤 (UNIT_000001)' -> 'UNIT_000001'
    fallback -> original stripped label
    """
    s = str(label).strip()
    if "(" in s and s.endswith(")"):
        inside = s.split("(")[-1].rstrip(")").strip()
        return inside if inside else s
    return s


# ============================================================
# Mobile / compact UI style (IMPORTANT)
# ============================================================

def apply_mobile_compact_style(max_width_px: int = 760):
    st.markdown(
        f"""
        <style>
        /* Make main container centered + not too wide on mobile */
        [data-testid="stMainBlockContainer"] {{
            max-width: {max_width_px}px !important;
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
            margin: 0 auto !important;
        }}

        /* Hide number input +/- steppers */
        div[data-testid="stNumberInputStepUp"],
        div[data-testid="stNumberInputStepDown"] {{ display: none !important; }}
        input[type=number] {{
            -moz-appearance: textfield !important;
            -webkit-appearance: none !important;
            margin: 0 !important;
        }}

        /* Keep columns on one line as much as possible */
        [data-testid="stHorizontalBlock"] {{
            gap: 0.4rem !important;
            flex-wrap: nowrap !important;
            align-items: center !important;
        }}
        [data-testid="column"] {{ min-width: 0 !important; }}

        /* Compact dataframe */
        [data-testid="stDataFrame"] [role="gridcell"],
        [data-testid="stDataFrame"] [role="columnheader"] {{
            padding: 4px 4px !important;
            font-size: 12px !important;
            line-height: 1.1 !important;
        }}

        /* Slightly tighten captions */
        .stCaption {{ margin-top: -0.25rem !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header():
    st.title("ORIVIA OMS Admin UI")
    st.caption("BUILD: stable + cache + actor + rbac + mobile-compact")


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
    """
    Best-effort exponential backoff wrapper for gspread calls.
    Prevents bursty rate-limit errors from killing UX.
    """
    last_err = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last_err = e
            # Backoff: 0.7s, 1.4s, 2.8s...
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
        """
        Batch append rows (reduces API calls).
        """
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


def read_table_with_rownum(sheet_id: str, table: str) -> pd.DataFrame:
    bust = int(st.session_state.get("cache_bust", 0))
    values = cached_table_values(sheet_id, table, bust)
    if not values:
        return pd.DataFrame()
    header = values[0]
    rows = values[1:]
    df = pd.DataFrame(rows, columns=header)
    df["_row"] = list(range(2, 2 + len(rows)))  # header row=1
    return df


# ============================================================
# Audit (best-effort)
# ============================================================

def try_append_audit(repo: GoogleSheetsRepo, audit_sheet: str, actor_user_id: str, action: str, entity: str, detail: str):
    try:
        ws = repo.get_ws(audit_sheet)
        values = _with_backoff(lambda: ws.get_all_values(), desc=f"audit_get_all:{audit_sheet}")
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
        _with_backoff(lambda: ws.append_row(out, value_input_option="USER_ENTERED"), desc=f"audit_append:{audit_sheet}")
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
# Admin Pages
# ============================================================

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

    units_df = read_table(sheet_id, "units")
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


def page_items_create(repo: GoogleSheetsRepo, sheet_id: str, env: str, actor_user_id: str):
    require_role("Admin", role_of(actor_user_id))

    st.subheader("Admin / Items / Create")
    st.markdown("### 新增品項")

    vendors_df = read_table(sheet_id, "vendors")
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

    units_df = read_table(sheet_id, "units")
    unit_options = build_unit_options(units_df)
    unit_label_to_id = {u: _extract_id_from_label(u) for u in unit_options}

    col_u1, col_u2 = st.columns(2)
    with col_u1:
        stock_unit_label = st.selectbox("庫存單位 stock_unit", options=unit_options)
    with col_u2:
        order_unit_label = st.selectbox("叫貨單位 order_unit", options=unit_options)

    stock_unit = unit_label_to_id.get(stock_unit_label, "").strip()
    order_unit = unit_label_to_id.get(order_unit_label, "").strip()

    item_name = st.text_input("品項名稱（內部） item_name", value="").strip()
    item_name_zh = st.text_input("中文名稱 item_name_zh", value=item_name).strip()
    item_name_en = st.text_input("英文名稱 item_name_en（可空）", value="").strip()
    item_code = st.text_input("品項代碼 item_code（可空）", value="").strip()
    is_active = st.checkbox("啟用", value=True)

    submit = st.button("✅ 建立品項", use_container_width=True)
    if not submit:
        return

    if not item_name:
        st.warning("請輸入 item_name")
        return
    if not stock_unit or not order_unit:
        st.warning("請選擇庫存單位與叫貨單位")
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


def page_items_list(repo: GoogleSheetsRepo, sheet_id: str, actor_user_id: str):
    require_role("Admin", role_of(actor_user_id))

    st.subheader("Admin / Items / List")

    df = read_table(sheet_id, "items")
    if df.empty:
        st.warning("items table 沒有資料")
        return

    st.dataframe(df, use_container_width=True)

    st.divider()
    st.markdown("### 🔎 選取一筆 → 顯示細節（目前先展示，不做編輯）")

    if "item_id" not in df.columns:
        st.error("items table 缺少 item_id 欄位")
        return

    pick = st.selectbox("item_id", options=df["item_id"].astype(str).tolist(), index=0, key="pick_item_id")
    row = df[df["item_id"].astype(str) == str(pick)]
    if not row.empty:
        st.success(f"你選到：{pick}")
        st.json(row.iloc[0].to_dict())


def page_prices_create(repo: GoogleSheetsRepo, sheet_id: str, env: str, actor_user_id: str, audit_sheet: str):
    require_role("Admin", role_of(actor_user_id))

    st.subheader("Admin / Prices / Create")
    st.markdown("### 新增價格（歷史價格）")

    items_df = read_table(sheet_id, "items")
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

    prices_df = read_table_with_rownum(sheet_id, "prices")
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

            repo.update_fields_by_row(
                "prices",
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
                audit_sheet=audit_sheet,
                actor_user_id=actor_user_id,
                action="PRICE_ROLLBACK",
                entity=str(item_id),
                detail=f"void={current_row.get('price_id','')}, restore={prev_row.get('price_id','')}",
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

    # Ensure header completeness
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
# Units: build dropdown options
# ============================================================

def build_unit_options(units_df: pd.DataFrame) -> list[str]:
    if units_df is None or units_df.empty:
        return ["(未設定單位)"]
    df = units_df.copy()
    if "is_active" in df.columns:
        df = df[df["is_active"].astype(str).str.upper() == "TRUE"]
    opts = []
    for _, r in df.iterrows():
        uid = str(r.get("unit_id", "")).strip()
        name = str(r.get("unit_name", "")).strip()
        if not uid:
            continue
        opts.append(f"{name} ({uid})" if name else uid)
    return opts or ["(未設定單位)"]


# ============================================================
# Stocktake/Order UI (your requested layout)
# ============================================================

def render_item_row_with_unit_dropdown(
    *,
    item_id: str,
    item_name: str,
    stock_unit_text: str | None,
    order_unit_text: str | None,
    price_today: float | None,
):
    """
    One row = Name | stock_qty + stock_unit_dropdown | order_qty + order_unit_dropdown
    Returns: stock_qty, stock_unit_label, order_qty, order_unit_label
    """

    # Name | stock qty | stock unit | order qty | order unit
    c_name, c_s_qty, c_s_unit, c_o_qty, c_o_unit = st.columns([7.2, 1.7, 1.6, 1.7, 1.6])

    with c_name:
        st.markdown(f"**{item_name}**")
        meta = []
        if stock_unit_text:
            meta.append(f"庫單位：{stock_unit_text}")
        if order_unit_text:
            meta.append(f"叫貨單位：{order_unit_text}")
        if price_today is not None:
            meta.append(f"單價(當日)：{price_today:.2f}")
        if meta:
            st.caption("｜".join(meta))
        st.code(item_id, language=None)

    with c_s_qty:
        stock_qty = st.number_input(
            "庫",
            min_value=0.0,
            step=0.1,
            value=0.0,
            key=f"stk_qty__{item_id}",
            label_visibility="collapsed",
        )

    with c_s_unit:
        stock_unit_label = st.selectbox(
            "庫單位",
            options=st.session_state["__unit_options"],
            index=st.session_state["__unit_index_map"].get(stock_unit_text or "", 0),
            key=f"stk_unit__{item_id}",
            label_visibility="collapsed",
        )

    with c_o_qty:
        order_qty = st.number_input(
            "進",
            min_value=0.0,
            step=0.1,
            value=0.0,
            key=f"ord_qty__{item_id}",
            label_visibility="collapsed",
        )

    with c_o_unit:
        order_unit_label = st.selectbox(
            "進單位",
            options=st.session_state["__unit_options"],
            index=st.session_state["__unit_index_map"].get(order_unit_text or "", 0),
            key=f"ord_unit__{item_id}",
            label_visibility="collapsed",
        )

    return float(stock_qty), stock_unit_label, float(order_qty), order_unit_label


def get_price_today(sheet_id: str, item_id: str, target_date: date) -> float:
    """
    prices table: item_id, unit_price, effective_date, end_date, is_active
    Choose the active record that covers target_date (end_date empty = ongoing).
    """
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
    tmp["__active"] = tmp["is_active"].apply(lambda x: (str(x).strip() == "" or str(x).strip().upper() == "TRUE")) if "is_active" in tmp.columns else True

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


def page_stocktake_order(repo: GoogleSheetsRepo, sheet_id: str, env: str, actor_user_id: str):
    """
    Writes to:
      - stocktakes (header row exists)
      - stocktake_lines (header row exists)
    """
    require_role("Admin", role_of(actor_user_id))  # 先鎖 admin；你要放給店長/PT 再調整

    apply_mobile_compact_style(max_width_px=760)

    st.subheader("點貨 / 叫貨")
    st.caption("品項名稱｜庫（數量+單位）｜進（數量+單位）—— 全部同一行，最後一次送出。")

    # Store selection (if you already have stores table)
    stores_df = read_table(sheet_id, "stores")
    store_opts = []
    if not stores_df.empty and "store_id" in stores_df.columns:
        # try store_name
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

    # Units options (shared)
    units_df = read_table(sheet_id, "units")
    unit_options = build_unit_options(units_df)
    unit_index_map = {u: i for i, u in enumerate(unit_options)}

    st.session_state["__unit_options"] = unit_options
    st.session_state["__unit_index_map"] = unit_index_map

    # Items list
    items_df = read_table(sheet_id, "items")
    if items_df.empty:
        st.warning("items 沒有資料，請先用 Admin / Items / Create 建立品項。")
        return

    # active only
    if "is_active" in items_df.columns:
        items_df = items_df[items_df["is_active"].astype(str).str.upper() == "TRUE"]

    # vendor filter
    if vendor_id and "vendor_id" in items_df.columns:
        items_df = items_df[items_df["vendor_id"].astype(str).str.strip() == vendor_id]

    if items_df.empty:
        st.info("此條件下沒有可用品項。")
        return

    # Choose display name
    def _item_display(r):
        if "item_name_zh" in items_df.columns and str(r.get("item_name_zh", "")).strip():
            return str(r.get("item_name_zh", "")).strip()
        if "item_name" in items_df.columns and str(r.get("item_name", "")).strip():
            return str(r.get("item_name", "")).strip()
        return str(r.get("item_id", "")).strip()

    # Render header row text (like your old UI "品項名稱 / 庫 / 進")
    h1, h2, h3, h4, h5 = st.columns([7.2, 1.7, 1.6, 1.7, 1.6])
    with h1:
        st.markdown("**品項名稱**")
    with h2:
        st.markdown("<div style='text-align:center;'><b>庫</b></div>", unsafe_allow_html=True)
    with h3:
        st.markdown("<div style='text-align:center;'><b>單位</b></div>", unsafe_allow_html=True)
    with h4:
        st.markdown("<div style='text-align:center;'><b>進</b></div>", unsafe_allow_html=True)
    with h5:
        st.markdown("<div style='text-align:center;'><b>單位</b></div>", unsafe_allow_html=True)

    st.divider()

    # Form: only ONE submit button (prevents quota burst)
    with st.form("stocktake_order_form", clear_on_submit=False):
        rows_out = []

        for _, r in items_df.iterrows():
            item_id = str(r.get("item_id", "")).strip()
            if not item_id:
                continue

            item_name = _item_display(r)

            # defaults from item master
            stock_unit_id = str(r.get("stock_unit", "")).strip() if "stock_unit" in items_df.columns else ""
            order_unit_id = str(r.get("order_unit", "")).strip() if "order_unit" in items_df.columns else ""

            # convert default ids into labels if possible
            def _id_to_label(uid: str) -> str:
                if not uid:
                    return unit_options[0]
                for u in unit_options:
                    if _extract_id_from_label(u) == uid:
                        return u
                return unit_options[0]

            default_stock_unit_label = _id_to_label(stock_unit_id)
            default_order_unit_label = _id_to_label(order_unit_id)

            price_today = get_price_today(sheet_id, item_id, record_date)

            stock_qty, stock_unit_label, order_qty, order_unit_label = render_item_row_with_unit_dropdown(
                item_id=item_id,
                item_name=item_name,
                stock_unit_text=default_stock_unit_label,
                order_unit_text=default_order_unit_label,
                price_today=price_today,
            )

            rows_out.append({
                "item_id": item_id,
                "item_name": item_name,
                "stock_qty": stock_qty,
                "stock_unit_id": _extract_id_from_label(stock_unit_label),
                "order_qty": order_qty,
                "order_unit_id": _extract_id_from_label(order_unit_label),
                "unit_price": float(price_today or 0.0),
            })

        note = st.text_area("備註（可空）", value="")

        submitted = st.form_submit_button("✅ 一次送出（寫入點貨+叫貨）", use_container_width=True)

    if not submitted:
        return

    # Filter: keep rows where any qty > 0 (avoid writing empty noise)
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

    # Write stocktakes (header must include these columns)
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

    # Write stocktake_lines rows
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
            "stock_qty": str(x["stock_qty"]),
            "stock_unit_id": x["stock_unit_id"],
            "order_qty": str(x["order_qty"]),
            "order_unit_id": x["order_unit_id"],
            "unit_price": str(x["unit_price"]),
            "amount": str(round(float(x["order_qty"]) * float(x["unit_price"]), 2)),
            "note": "",
            "created_at": now,
            "created_by": actor_user_id,
            "updated_at": "",
            "updated_by": "",
        })

    # Persist (batch append reduces rate limit)
    try:
        repo.append_row_dict("stocktakes", stocktake_row)
        repo.append_rows("stocktake_lines", lines)
        bust_cache()
        st.success(f"✅ 已送出成功：stocktake_id = {stocktake_id}（共 {len(lines)} 筆）")
    except Exception as e:
        st.error(f"寫入失敗（可能限流/欄位不匹配）：{e}")
        st.info("如果是限流：等 30~60 秒再試一次，或少量分批送出。")


# ============================================================
# Navigation (fix session_state issue)
# ============================================================

def _resolve_nav_target_before_widget(default_page: str):
    """
    Streamlit rule: can't set widget state after it is created in same run.
    So we use nav_target as an intermediate.
    """
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

        pages = []
        if is_admin:
            pages = [
                "Stocktake / Order",   # NEW
                "Vendors / Create",
                "Units / Create",
                "Items / Create",
                "Items / List",
                "Prices / Create",
            ]
        else:
            pages = ["(No Access)"]

        _resolve_nav_target_before_widget(default_page=pages[0])
        page = st.radio("Page", options=pages, key="nav_page")

    if page == "Stocktake / Order":
        page_stocktake_order(repo, sheet_id=sheet_id, env=env, actor_user_id=actor_user_id)

    elif page == "Vendors / Create":
        page_vendors_create(repo, sheet_id=sheet_id, env=env, actor_user_id=actor_user_id)

    elif page == "Units / Create":
        page_units_create(repo, sheet_id=sheet_id, env=env, actor_user_id=actor_user_id)

    elif page == "Items / Create":
        page_items_create(repo, sheet_id=sheet_id, env=env, actor_user_id=actor_user_id)

    elif page == "Items / List":
        page_items_list(repo, sheet_id=sheet_id, actor_user_id=actor_user_id)

    elif page == "Prices / Create":
        page_prices_create(repo, sheet_id=sheet_id, env=env, actor_user_id=actor_user_id, audit_sheet=audit_sheet)

    else:
        st.info("目前此角色沒有可用頁面。")


if __name__ == "__main__":
    st.set_page_config(page_title="ORIVIA OMS Admin UI", layout="wide")
    main()
