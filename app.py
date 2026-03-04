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

    def get_ws(self, table: str):
        return self.sh.worksheet(table)

    def read_table(self, table: str) -> pd.DataFrame:
        ws = self.get_ws(table)
        values = ws.get_all_values()
        if not values:
            return pd.DataFrame()
        header = values[0]
        rows = values[1:]
        return pd.DataFrame(rows, columns=header)

    def append_row_dict(self, table: str, row: dict):
        """
        依照 sheet header 欄位順序 append 一列（Fail Fast：缺欄位就報錯）
        """
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
        """
        以 row_index(1-based) 覆蓋整列（依 header 順序寫入）
        """
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
# ID Generator (from id_sequences)
# ============================================================

def _make_id(prefix: str, width: int, n: int) -> str:
    return f"{prefix}{str(n).zfill(int(width))}"


def get_next_id(repo: GoogleSheetsRepo, key: str, env: str, actor_user_id: str) -> str:
    """
    讀 id_sequences 取得 next_value，生成 ID，並把 next_value + 1 寫回
    Fail Fast：找不到 key/env 或欄位缺失直接報錯
    """
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

    # 找到實際在 sheet 的列號（1-based；含 header）
    # df index 是從 0 開始對應 rows[0] = sheet 第2列
    sheet_row_index = int(hit.index[0]) + 2

    # 更新 next_value + last_number/updated_at/updated_by（如果欄位存在就寫）
    updated = rec.copy()
    updated["next_value"] = str(next_value + 1)

    if "last_number" in updated:
        updated["last_number"] = str(next_value)

    if "updated_at" in updated:
        updated["updated_at"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    if "updated_by" in updated:
        updated["updated_by"] = actor_user_id

    # 補齊缺欄位（避免 update_row Fail）
    for c in header:
        if c not in updated:
            updated[c] = ""

    repo.update_row("id_sequences", sheet_row_index, updated)

    return new_id


# ============================================================
# Pages (minimal)
# ============================================================

def page_vendors_create(repo: GoogleSheetsRepo, env: str, actor_user_id: str):
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

    try:
        vendor_id = get_next_id(repo, key="vendors", env=env, actor_user_id=actor_user_id)
    except Exception as e:
        fail(f"取得 vendor_id 失敗：{e}")

    # 依你 vendors 表欄位（完整版）寫入：缺欄位就 Fail Fast
    now = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    new_vendor = {
        "vendor_id": vendor_id,
        "brand_id": "",          # 先留空（下一步接 brands 下拉）
        "vendor_name": vendor_name,
        "is_active": str(bool(is_active)),
        "audit": "",
        "note": "",
        "created_at": now,
        "created_by": actor_user_id,
        "updated_at": "",
        "updated_by": "",
    }

    try:
        repo.append_row_dict("vendors", new_vendor)
    except Exception as e:
        fail(f"寫入 vendors 失敗：{e}")

    st.success(f"✅ 建立成功：{vendor_name}（{vendor_id}）")
    st.json(new_vendor)

def page_items_create(repo: GoogleSheetsRepo, env: str, actor_user_id: str):
    st.subheader("Admin / Items / Create")
    st.markdown("### 新增品項")

    # ----------------------------
    # 1) Vendors 下拉（只顯示啟用）
    # ----------------------------
    vendors_df = repo.read_table("vendors")
    if vendors_df.empty:
        st.warning("沒有 vendors，請先建立廠商")
        return

    if "is_active" in vendors_df.columns:
        vendors_df = vendors_df[vendors_df["is_active"] == "TRUE"]

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

    # ----------------------------
    # 2) Units 下拉（雙單位：庫存/叫貨）
    # ----------------------------
    units_df = repo.read_table("units")
    unit_options = []

    if not units_df.empty:
        # 常見欄位：unit_id / unit_name / is_active
        if "is_active" in units_df.columns:
            units_df = units_df[units_df["is_active"] == "TRUE"]

        if "unit_id" in units_df.columns:
            # 顯示：name (UNIT_000001)
            def _label(r):
                name = r.get("unit_name", "") if "unit_name" in units_df.columns else ""
                uid = r.get("unit_id", "")
                return f"{name} ({uid})" if name else str(uid)

            unit_map = { _label(r): r.get("unit_id", "") for _, r in units_df.iterrows() }
            unit_options = list(unit_map.keys())
        else:
            unit_map = {}
    else:
        unit_map = {}

    col_u1, col_u2 = st.columns(2)
    with col_u1:
        stock_unit = st.selectbox("庫存單位 stock_unit", options=unit_options) if unit_options else st.text_input("庫存單位 stock_unit（先手輸入）")
    with col_u2:
        order_unit = st.selectbox("叫貨單位 order_unit", options=unit_options) if unit_options else st.text_input("叫貨單位 order_unit（先手輸入）")

    if unit_options:
        stock_unit = unit_map.get(stock_unit, "")
        order_unit = unit_map.get(order_unit, "")

    # ----------------------------
    # 3) 品項欄位（最少可用）
    # ----------------------------
    item_name = st.text_input("品項名稱（內部） item_name", value="").strip()
    item_name_zh = st.text_input("中文名稱 item_name_zh", value=item_name).strip()
    item_name_en = st.text_input("英文名稱 item_name_en（可空）", value="").strip()
    item_code = st.text_input("品項代碼 item_code（可空）", value="").strip()
    is_active = st.checkbox("啟用", value=True)

    # brand_id：先給空（下一步接 brands 下拉）
    brand_id = ""

    submit = st.button("建立品項", use_container_width=True)

    if not submit:
        return

    # ----------------------------
    # Fail Fast 檢查
    # ----------------------------
    if not item_name:
        st.warning("請輸入 item_name")
        return

    if not stock_unit or not order_unit:
        st.warning("請選擇（或填寫）庫存單位與叫貨單位")
        return

    # ----------------------------
    # 4) 產生 item_id + 寫入 items
    # ----------------------------
    try:
        item_id = get_next_id(repo, key="items", env=env, actor_user_id=actor_user_id)
    except Exception as e:
        fail(f"取得 item_id 失敗：{e}")

    now = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    new_item = {
        "item_id": item_id,
        "brand_id": brand_id,
        "vendor_id": vendor_id,
        "item_code": item_code,
        "item_name": item_name,
        "item_name_zh": item_name_zh,
        "item_name_en": item_name_en,
        "stock_unit": stock_unit,
        "order_unit": order_unit,
        "is_active": str(bool(is_active)),
        "audit": "",
        "note": "",
        "created_at": now,
        "created_by": actor_user_id,
        "updated_at": "",
        "updated_by": "",
    }

    try:
        repo.append_row_dict("items", new_item)
    except Exception as e:
        fail(f"寫入 items 失敗：{e}")

    st.success(f"✅ 建立成功：{item_name}（{item_id}）")
    st.json(new_item)



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


def page_prices_create(repo: GoogleSheetsRepo, env: str, actor_user_id: str):
    st.subheader("Admin / Prices / Create")
    st.markdown("### 新增價格（歷史價格）")

    # ----------------------------
    # 1) Items 下拉（只顯示啟用）
    # ----------------------------
    items_df = repo.read_table("items")
    if items_df.empty:
        st.warning("沒有 items，請先建立品項")
        return

    if "is_active" in items_df.columns:
        items_df = items_df[items_df["is_active"] == "TRUE"]

    # 顯示名稱優先：item_name_zh > item_name > item_id
    def _item_label(r):
        name = ""
        if "item_name_zh" in items_df.columns and str(r.get("item_name_zh", "")).strip():
            name = str(r.get("item_name_zh", "")).strip()
        elif "item_name" in items_df.columns and str(r.get("item_name", "")).strip():
            name = str(r.get("item_name", "")).strip()
        iid = str(r.get("item_id", "")).strip()
        return f"{name} ({iid})" if name else iid

    item_map = { _item_label(r): r.get("item_id", "") for _, r in items_df.iterrows() if str(r.get("item_id","")).strip() }
    if not item_map:
        st.warning("沒有可用品項（items.is_active=TRUE）")
        return

    item_label = st.selectbox("選擇品項", options=list(item_map.keys()))
    item_id = item_map[item_label]

    # ----------------------------
    # 2) 價格輸入
    # ----------------------------
    unit_price = st.number_input("單價 unit_price", min_value=0.0, step=1.0, format="%.2f")

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        effective_date = st.date_input("生效日 effective_date")
    with col_d2:
        end_date = st.date_input("失效日 end_date（可空）", value=None)

    is_active = st.checkbox("啟用 (is_active)", value=True)

    submit = st.button("建立價格", use_container_width=True)
    if not submit:
        return

    if unit_price <= 0:
        st.warning("單價必須 > 0")
        return

    # ----------------------------
    # 3) 簡版防重疊：如果 prices 已有此 item 的「現行價（end_date 空）」且你也要新增現行價 → 擋
    # ----------------------------
    prices_df = repo.read_table("prices")
    if not prices_df.empty and "item_id" in prices_df.columns:
        cur = prices_df[
            (prices_df["item_id"].astype(str) == str(item_id)) &
            ((prices_df.get("end_date", "") == "") | prices_df.get("end_date", "").isna())
        ]
        if len(cur) > 0 and end_date is None:
            st.error("⚠️ 此品項已有一筆現行價（end_date 空）。請先把舊價格補 end_date，再新增新的現行價。")
            st.stop()

    # ----------------------------
    # 4) 產生 price_id + 寫入 prices
    # ----------------------------
    try:
        price_id = get_next_id(repo, key="prices", env=env, actor_user_id=actor_user_id)
    except Exception as e:
        fail(f"取得 price_id 失敗：{e}")

    now = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    new_price = {
        "price_id": price_id,
        "brand_id": "",              # 先留空（之後接 brands）
        "vendor_id": "",             # 先留空（之後可從 items join 補）
        "item_id": item_id,
        "unit_price": str(unit_price),
        "effective_date": str(effective_date),
        "end_date": "" if end_date is None else str(end_date),
        "is_active": str(bool(is_active)),
        "audit": "",
        "note": "",
        "created_at": now,
        "created_by": actor_user_id,
        "updated_at": "",
        "updated_by": "",
    }

    # 自動補齊 header（避免 prices 表未來加欄位又擋）
    try:
        ws = repo.get_ws("prices")
        header = ws.get_all_values()[0]
        for c in header:
            if c not in new_price:
                new_price[c] = ""
    except Exception as e:
        fail(f"讀取 prices header 失敗：{e}")

    try:
        repo.append_row_dict("prices", new_price)
    except Exception as e:
        fail(f"寫入 prices 失敗：{e}")

    st.success(f"✅ 建立成功：{item_label} / {unit_price}（{price_id}）")
    st.json(new_price)

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
        page_vendors_create(repo, env=env, actor_user_id=auth["user_id"])
    elif page == "Items / Create":
        page_items_create(repo, env=env, actor_user_id=auth["user_id"])
    elif page == "Items / List":
        page_items_list(repo)
    elif page == "Items / Edit":
        page_items_edit(repo, pipe, actor_user_id=auth["user_id"], env=env)
    elif page == "Prices / Create":
        page_prices_create(repo, env=env, actor_user_id=auth["user_id"])


if __name__ == "__main__":
    st.set_page_config(page_title="ORIVIA OMS Admin UI", layout="wide")
    main()



