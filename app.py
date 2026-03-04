# ============================================================
# ORIVIA OMS Admin UI (Stable + Cache + Actor Selector + RBAC)
# 單檔 app.py：可上 GitHub + Streamlit Cloud 測試
#
# ✅ 你要的：方案1（UI選操作者）可直接上線
# - Sidebar：actor_user_id 下拉（OWNER / ADMIN_01~03）
# - role mapping：Owner / Admin
# - 基礎 RBAC：Admin 以上才能進 Vendors/Items/Prices
# - 保留：Cache（避免 quota）、Prices Rollback、Audit best-effort
#
# ✅ 之後升級方案2（登入/權限）：
# 只要把 actor_user_id 改成 auth["user_id"]，role 改成查 users 表即可
# ============================================================

from __future__ import annotations

from pathlib import Path
from datetime import timedelta, date
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials


# ============================================================
# Basic helpers
# ============================================================

def fail(msg: str):
    st.error(msg)
    st.stop()


def page_header():
    st.title("ORIVIA OMS Admin UI")
    st.caption("BUILD: stable + cache + actor + rbac")


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
    """
    永遠回傳 datetime.date 或 None（避免 date/datetime 混用）
    """
    s = str(s).strip()
    if not s:
        return None
    try:
        return pd.to_datetime(s, errors="raise").date()
    except Exception:
        return None


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
# Repo (Google Sheets)
# ============================================================

class GoogleSheetsRepo:
    def __init__(self, sheet_id: str, creds_path: str | None = None):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        # Streamlit Cloud：用 secrets（不需要檔案）
        if "gcp" in st.secrets:
            creds = Credentials.from_service_account_info(st.secrets["gcp"], scopes=scopes)
        else:
            # 本機：用 json 檔案路徑
            if not creds_path:
                raise FileNotFoundError("Missing creds_path (service_account.json path)")
            p = Path(creds_path)
            if not p.exists():
                raise FileNotFoundError(f"No such file: {p}")
            creds = Credentials.from_service_account_file(str(p), scopes=scopes)

        gc = gspread.authorize(creds)
        self.sh = gc.open_by_key(sheet_id)

    def get_ws(self, table: str):
        return self.sh.worksheet(table)

    def fetch_all_values(self, table: str) -> list[list[str]]:
        ws = self.get_ws(table)
        return ws.get_all_values()

    def append_row_dict(self, table: str, row: dict):
        ws = self.get_ws(table)
        values = ws.get_all_values()
        if not values:
            raise ValueError(f"Table '{table}' has no header row.")
        header = values[0]

        missing = [c for c in header if c not in row]
        if missing:
            raise ValueError(f"Append '{table}' missing fields: {missing}")

        out = [row.get(c, "") for c in header]
        ws.append_row(out, value_input_option="USER_ENTERED")

    def update_row(self, table: str, row_index_1based: int, new_row: dict):
        ws = self.get_ws(table)
        values = ws.get_all_values()
        if not values:
            raise ValueError(f"Table '{table}' has no header row.")
        header = values[0]

        missing = [c for c in header if c not in new_row]
        if missing:
            raise ValueError(f"Update '{table}' missing fields: {missing}")

        row_values = [new_row.get(c, "") for c in header]
        start = gspread.utils.rowcol_to_a1(row_index_1based, 1)
        end = gspread.utils.rowcol_to_a1(row_index_1based, len(header))
        ws.update(f"{start}:{end}", [row_values], value_input_option="USER_ENTERED")

    def update_fields_by_row(self, table: str, row_index_1based: int, patch: dict):
        ws = self.get_ws(table)
        values = ws.get_all_values()
        if not values:
            raise ValueError(f"Table '{table}' has no header row.")
        header = values[0]

        row_vals = ws.row_values(row_index_1based)
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
    df["_row"] = list(range(2, 2 + len(rows)))  # header row=1
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
        values = ws.get_all_values()
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
        ws.append_row(out, value_input_option="USER_ENTERED")
    except Exception:
        return


# ============================================================
# ID Generator (from id_sequences)
# ============================================================

def _make_id(prefix: str, width: int, n: int) -> str:
    return f"{prefix}{str(n).zfill(int(width))}"


def get_next_id(repo: GoogleSheetsRepo, key: str, env: str, actor_user_id: str) -> str:
    ws = repo.get_ws("id_sequences")
    values = ws.get_all_values()
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
# Pages (Admin only)
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

    # Fail-fast: unit_name 必須唯一（避免重複）
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


def page_items_list(repo: GoogleSheetsRepo, sheet_id: str, actor_user_id: str):
    require_role("Admin", role_of(actor_user_id))

    st.subheader("Admin / Items / List")

    df = read_table(repo, sheet_id, "items")
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
        st.session_state["nav_page"] = "Items / Edit"
        st.rerun()


def page_items_edit(repo: GoogleSheetsRepo, sheet_id: str, actor_user_id: str):
    require_role("Admin", role_of(actor_user_id))

    st.subheader("Admin / Items / Edit")

    item_id = st.session_state.get("edit_item_id")
    if not item_id:
        st.info("請先到 Items / List 選一筆，再進 Edit。")
        return

    df = read_table(repo, sheet_id, "items")
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


def page_prices_create(repo: GoogleSheetsRepo, sheet_id: str, env: str, actor_user_id: str, audit_sheet: str):
    require_role("Admin", role_of(actor_user_id))  # ✅ 店長不能改價格（你選 A）

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

    try:
        ws = repo.get_ws("prices")
        header = ws.get_all_values()[0]
        for c in header:
            if c not in new_price:
                new_price[c] = ""
    except Exception as e:
        fail(f"讀取 prices header 失敗：{e}")

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
# Main
# ============================================================

def main():
    page_header()

    sheet_id, creds_path, env, audit_sheet = sidebar_system_config()
    actor_user_id, actor_role = sidebar_actor_selector()

    if not sheet_id:
        fail("Sheet ID 不能空白。")

    # 本機才檢查 creds_path
    if "gcp" not in st.secrets:
        if not creds_path:
            fail("本機測試：Service Account JSON Path 不能空白。")
        if not Path(creds_path).exists():
            fail(f"找不到 service_account.json：{creds_path}")

    # repo cache_resource：避免重複初始化導致 quota 爆
    try:
        repo = get_repo_cached(sheet_id, creds_path if "gcp" not in st.secrets else None)
    except Exception as e:
        fail(f"Repo 初始化失敗：{e}")

    with st.sidebar:
        st.divider()
        st.subheader("📚 Navigation")

        # ✅ 基礎頁面鎖：只有 Admin 以上才顯示 Admin Pages
        is_admin = ROLE_RANK.get(actor_role, 0) >= ROLE_RANK["Admin"]

        if is_admin:
            pages = [
                "Vendors / Create",
                "Units / Create",
                "Items / Create",
                "Items / List",
                "Items / Edit",
                "Prices / Create",
            ]
        else:
            pages = ["(No Access)"]

        page = st.radio("Page", options=pages, key="nav_page", index=0)

    if page == "Vendors / Create":
    page_vendors_create(repo, sheet_id=sheet_id, env=env, actor_user_id=actor_user_id)

elif page == "Units / Create":
    page_units_create(repo, sheet_id=sheet_id, env=env, actor_user_id=actor_user_id)

elif page == "Items / Create":
    page_items_create(repo, sheet_id=sheet_id, env=env, actor_user_id=actor_user_id)

elif page == "Items / List":
    page_items_list(repo, sheet_id=sheet_id, actor_user_id=actor_user_id)

elif page == "Items / Edit":
    page_items_edit(repo, sheet_id=sheet_id, actor_user_id=actor_user_id)

elif page == "Prices / Create":
    page_prices_create(repo, sheet_id=sheet_id, env=env, actor_user_id=actor_user_id, audit_sheet=audit_sheet)

else:
    st.info("目前此角色沒有可用頁面。")

if __name__ == "__main__":
    st.set_page_config(page_title="ORIVIA OMS Admin UI", layout="wide")
    main()

