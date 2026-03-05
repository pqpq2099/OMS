# ============================================================
# ORIVIA OMS Admin UI (Stable + Cache + Actor Selector + RBAC)
# + [NEW] Stocktake / Order (mobile 1-row layout)
#
# 單檔 app.py：可上 GitHub + Streamlit Cloud 測試
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


def page_header():
    st.title("ORIVIA OMS Admin UI")
    st.caption("BUILD: stable + cache + actor + rbac + stocktake/order (mobile rows)")


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

    def append_row_any(self, table: str, row: dict):
        """
        ✅ 不要求 row 一定包含全部 header 欄位
        - 以 sheet header 為準
        - 缺的補空字串
        - 多的忽略
        """
        ws = self.get_ws(table)
        values = ws.get_all_values()
        if not values:
            raise ValueError(f"Table '{table}' has no header row.")
        header = values[0]
        out = [row.get(c, "") for c in header]
        ws.append_row(out, value_input_option="USER_ENTERED")

    def update_row_any(self, table: str, row_index_1based: int, row: dict):
        ws = self.get_ws(table)
        values = ws.get_all_values()
        if not values:
            raise ValueError(f"Table '{table}' has no header row.")
        header = values[0]
        out = [row.get(c, "") for c in header]

        start = gspread.utils.rowcol_to_a1(row_index_1based, 1)
        end = gspread.utils.rowcol_to_a1(row_index_1based, len(header))
        ws.update(f"{start}:{end}", [out], value_input_option="USER_ENTERED")


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


def read_table(sheet_id: str, table: str) -> pd.DataFrame:
    bust = int(st.session_state.get("cache_bust", 0))
    values = cached_table_values(sheet_id, table, bust)
    if not values:
        return pd.DataFrame()
    header = values[0]
    rows = values[1:]
    return pd.DataFrame(rows, columns=header)


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


def get_next_id(repo: GoogleSheetsRepo, sheet_id: str, key: str, env: str, actor_user_id: str) -> str:
    df = read_table(sheet_id, "id_sequences")
    if df.empty:
        raise ValueError
