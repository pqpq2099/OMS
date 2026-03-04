# ============================================================
# ORIVIA OMS Admin UI (Minimal Complete Version)
# 單檔 app.py：可上 GitHub + Streamlit Cloud 測試
# ============================================================

from __future__ import annotations

from pathlib import Path
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials


# ============================================================
# Repo
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

        # 本機：用 json 檔案路徑
        else:
            if not creds_path:
                raise FileNotFoundError("Missing creds_path (service_account.json path)")
            p = Path(creds_path)
            if not p.exists():
                raise FileNotFoundError(f"No such file: {p}")
            creds = Credentials.from_service_account_file(str(p), scopes=scopes)

        gc = gspread.authorize(creds)
        self.sh = gc.open_by_key(sheet_id)

    def read_table(self, table: str) -> pd.DataFrame:
        ws = self.sh.worksheet(table)
        values = ws.get_all_values()
        if not values:
            return pd.DataFrame()
        header = values[0]
        rows = values[1:]
        return pd.DataFrame(rows, columns=header)


# ============================================================
# Basic helpers
# ============================================================

def page_header():
    st.title("ORIVIA OMS Admin UI")


def fail(msg: str):
    st.error(msg)
    st.stop()


def ensure_login():
    # 先用簡化登入（之後再接 users/roles）
    return {"user_id": "OWNER", "role": "Owner"}


def sidebar_system_config():
    with st.sidebar:
        st.subheader("System Config")

        sheet_id = st.text_input(
            "Sheet ID",
            value="1L1ogNjLWjjH8usMWC2JQowMMZkfD4zkuE-4UcgiTqXQ",
        )

        # Cloud 會用 secrets，不需要這個檔案，但留著給本機測試
        creds_path = st.text_input(
            "Service Account JSON Path (local only)",
            value="secrets/service_account.json",
        )

        env = st.text_input("ENV", value="prod")
        audit_sheet = st.text_input("Audit Sheet", value="audit_log_test")

        st.caption("✅ Streamlit Cloud 會自動用 st.secrets['gcp']，不看本機路徑。")

    return sheet_id.strip(), creds_path.strip(), env.strip(), audit_sheet.strip()


def build_services(sheet_id: str, creds_path: str, env: str, audit_sheet: str):
    # Cloud：creds_path 不會用到，但也不會出錯
    repo = GoogleSheetsRepo(sheet_id=sheet_id, creds_path=creds_path)
    pipe = None
    return repo, None, None, pipe


# ============================================================
# Pages (minimal)
# ============================================================

def page_vendors_create(pipe, actor_user_id: str):
    st.subheader("Admin / Vendors / Create")
    st.info("Vendor create UI placeholder")


def page_items_create(pipe, actor_user_id: str):
    st.subheader("Admin / Items / Create")
    st.info("Item create UI placeholder")


def page_items_list(repo: GoogleSheetsRepo):
    st.subheader("Admin / Items / List")

    df = repo.read_table("items")
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


def page_items_edit(repo: GoogleSheetsRepo, pipe, actor_user_id: str, env: str):
    st.subheader("Admin / Items / Edit")

    item_id = st.session_state.get("edit_item_id")
    if not item_id:
        st.info("請先到 Items / List 選一筆，再進 Edit。")
        return

    df = repo.read_table("items")
    if df.empty:
        st.warning("items table 沒資料")
        return

    if "item_id" not in df.columns:
        st.error("items table 缺少 item_id 欄位")
        return

    row = df[df["item_id"].astype(str) == str(item_id)]
    if row.empty:
        st.error(f"找不到 item_id：{item_id}")
        return

    rec = row.iloc[0].to_dict()
    st.success(f"目前編輯：{item_id}")
    st.json(rec)  # 先用最直觀方式顯示


def page_prices_create(repo: GoogleSheetsRepo, pipe, actor_user_id: str, env: str):
    st.subheader("Admin / Prices / Create")
    st.info("Price create UI placeholder")


# ============================================================
# Main
# ============================================================

def main():
    page_header()

    sheet_id, creds_path, env, audit_sheet = sidebar_system_config()
    auth = ensure_login()

    if not sheet_id:
        fail("Sheet ID 不能空白。")

    # 本機才檢查檔案存在；Cloud 用 secrets，不檢查
    if "gcp" not in st.secrets:
        if not creds_path:
            fail("本機測試：Service Account JSON Path 不能空白。")
        if not Path(creds_path).exists():
            fail(f"找不到 service_account.json：{creds_path}")

    try:
        repo, _, _, pipe = build_services(sheet_id, creds_path, env, audit_sheet)
    except Exception as e:
        fail(f"Repo 初始化失敗：{e}")

    with st.sidebar:
        st.divider()
        st.subheader("📚 Navigation")

        page = st.radio(
            "Page",
            options=[
                "Vendors / Create",
                "Items / Create",
                "Items / List",
                "Items / Edit",
                "Prices / Create",
            ],
            key="nav_page",
            index=0,
        )

    if page == "Vendors / Create":
        page_vendors_create(pipe, actor_user_id=auth["user_id"])
    elif page == "Items / Create":
        page_items_create(pipe, actor_user_id=auth["user_id"])
    elif page == "Items / List":
        page_items_list(repo)
    elif page == "Items / Edit":
        page_items_edit(repo, pipe, actor_user_id=auth["user_id"], env=env)
    elif page == "Prices / Create":
        page_prices_create(repo, pipe, actor_user_id=auth["user_id"], env=env)


if __name__ == "__main__":
    st.set_page_config(page_title="ORIVIA OMS Admin UI", layout="wide")
    main()
