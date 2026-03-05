# ============================================================
# ORIVIA OMS Admin UI (Stable)
# + 點貨 / 叫貨（同頁、手機一行版）
# ============================================================

from __future__ import annotations
from pathlib import Path
from datetime import date
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials


# ============================================================
# 基本工具
# ============================================================

def _now_ts():
    return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")


def _to_bool_str(v: bool):
    return "TRUE" if v else "FALSE"


def page_header():
    st.title("ORIVIA OMS Admin UI")
    st.caption("BUILD: stocktake / order mobile layout")


# ============================================================
# Sidebar
# ============================================================

def sidebar_system_config():
    with st.sidebar:
        st.subheader("System Config")

        sheet_id = st.text_input(
            "Sheet ID",
            value="1L1ogNjLWjjH8usMWC2JQowMMZkfD4zkuE-4UcgiTqXQ",
        )

        creds_path = st.text_input(
            "Service Account JSON Path (local only)",
            value="secrets/service_account.json",
        )

        env = st.text_input("ENV", value="prod")

        st.caption("Streamlit Cloud 會自動用 st.secrets['gcp']")

    return sheet_id, creds_path, env


# ============================================================
# Google Sheets Repo
# ============================================================

class GoogleSheetsRepo:

    def __init__(self, sheet_id: str, creds_path: str | None):

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        if "gcp" in st.secrets:
            creds = Credentials.from_service_account_info(
                st.secrets["gcp"],
                scopes=scopes
            )
        else:
            p = Path(creds_path)
            creds = Credentials.from_service_account_file(str(p), scopes=scopes)

        gc = gspread.authorize(creds)
        self.sh = gc.open_by_key(sheet_id)

    def ws(self, name):
        return self.sh.worksheet(name)

    def fetch_all(self, table):

        values = self.ws(table).get_all_values()

        if not values:
            return pd.DataFrame()

        header = values[0]
        rows = values[1:]

        return pd.DataFrame(rows, columns=header)

    def append(self, table, row: dict):

        ws = self.ws(table)
        header = ws.get_all_values()[0]

        out = [row.get(c, "") for c in header]

        ws.append_row(out, value_input_option="USER_ENTERED")


# ============================================================
# Cache
# ============================================================

@st.cache_resource
def get_repo(sheet_id, creds_path):
    return GoogleSheetsRepo(sheet_id, creds_path)


@st.cache_data(ttl=60)
def read_table(sheet_id, table):

    repo = get_repo(sheet_id, None)

    df = repo.fetch_all(table)

    return df


# ============================================================
# Mobile row CSS
# ============================================================

def apply_mobile_row_style():

    st.markdown(
        """
<style>

[data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    gap: 0.5rem;
}

input[type=number]::-webkit-inner-spin-button,
input[type=number]::-webkit-outer-spin-button {
    display:none;
}

.block-container {
    padding-left:0.5rem;
    padding-right:0.5rem;
}

</style>
""",
        unsafe_allow_html=True,
    )


# ============================================================
# Row render（核心）
# ============================================================

def render_item_row(item_id, name, stock_unit, order_unit, price):

    col_name, col_stock, col_order = st.columns([7,2,2])

    with col_name:

        st.markdown(f"**{name}**")
        st.caption(f"庫:{stock_unit}｜叫:{order_unit}｜單價:{price}")

    with col_stock:

        stock = st.number_input(
            "庫",
            key=f"stk_{item_id}",
            min_value=0.0,
            step=0.1,
            label_visibility="collapsed"
        )

    with col_order:

        order = st.number_input(
            "進",
            key=f"ord_{item_id}",
            min_value=0.0,
            step=0.1,
            label_visibility="collapsed"
        )

    return stock, order


# ============================================================
# 點貨 / 叫貨頁
# ============================================================

def page_stock_order(repo, sheet_id, env):

    apply_mobile_row_style()

    st.subheader("點貨 / 叫貨")

    items = read_table(sheet_id, "items")
    prices = read_table(sheet_id, "prices")

    if items.empty:
        st.warning("items 沒資料")
        return

    price_map = {}

    for _, r in prices.iterrows():
        price_map[r["item_id"]] = r["unit_price"]

    st.divider()

    rows = []

    with st.form("stock_order_form"):

        for _, r in items.iterrows():

            item_id = r["item_id"]

            name = r.get("item_name_zh") or r.get("item_name")

            stock_unit = r.get("stock_unit", "")

            order_unit = r.get("order_unit", "")

            price = price_map.get(item_id, "")

            stock, order = render_item_row(
                item_id,
                name,
                stock_unit,
                order_unit,
                price
            )

            rows.append((item_id, stock, order))

        note = st.text_input("備註")

        submit = st.form_submit_button("✅ 一次送出")

    if submit:

        now = _now_ts()

        stocktake_id = f"STK_{now}"

        po_id = f"PO_{now}"

        for item_id, stock, order in rows:

            if stock > 0:

                repo.append(
                    "stocktake_lines",
                    {
                        "stocktake_id": stocktake_id,
                        "item_id": item_id,
                        "qty": stock,
                        "created_at": now,
                    }
                )

            if order > 0:

                repo.append(
                    "purchase_order_lines",
                    {
                        "po_id": po_id,
                        "item_id": item_id,
                        "qty": order,
                        "created_at": now,
                    }
                )

        st.success("已送出")


# ============================================================
# MAIN
# ============================================================

def main():

    page_header()

    sheet_id, creds_path, env = sidebar_system_config()

    repo = get_repo(sheet_id, creds_path)

    with st.sidebar:

        st.subheader("Navigation")

        page = st.radio(
            "Page",
            [
                "點貨 / 叫貨",
            ]
        )

    if page == "點貨 / 叫貨":

        page_stock_order(repo, sheet_id, env)


if __name__ == "__main__":

    st.set_page_config(
        page_title="ORIVIA OMS",
        layout="wide"
    )

    main()
