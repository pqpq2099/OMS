from __future__ import annotations

import streamlit as st

from oms_core import (
    _get_active_df,
    _norm,
    _now_ts,
    allocate_ids,
    append_rows_by_header,
    get_header,
    read_table,
    bust_cache,
)


# ============================================================
# Admin Home
# ============================================================

def page_admin_home():

    st.title("⚙️ 系統管理")

    if st.button("🏢 廠商管理", use_container_width=True):
        st.session_state.step = "admin_vendors"
        st.rerun()

    if st.button("📦 品項管理", use_container_width=True):
        st.session_state.step = "admin_items"
        st.rerun()

    if st.button("💰 價格管理", use_container_width=True):
        st.session_state.step = "admin_prices"
        st.rerun()

    if st.button("🔄 單位換算", use_container_width=True):
        st.session_state.step = "admin_units"
        st.rerun()


# ============================================================
# Vendors
# ============================================================

def page_admin_vendors():

    st.title("🏢 廠商管理")

    vendors_df = read_table("vendors")

    if vendors_df.empty:
        st.warning("vendors 資料讀取失敗")
        return

    # --------------------------------------------------------
    # 新增廠商
    # --------------------------------------------------------

    st.subheader("新增廠商")

    with st.form("add_vendor_form"):

        vendor_name = st.text_input("廠商名稱")

        submitted = st.form_submit_button("新增廠商")

    if submitted:

        if not vendor_name.strip():
            st.warning("請輸入廠商名稱")
            return

        try:

            id_map = allocate_ids({"vendor_id": 1})

            vendor_id = id_map["vendor_id"][0]

            header = get_header("vendors")

            row = {c: "" for c in header}

            now = _now_ts()

            defaults = {
                "vendor_id": vendor_id,
                "vendor_name": vendor_name.strip(),
                "is_active": True,
                "created_at": now,
                "created_by": "ADMIN",
                "updated_at": "",
                "updated_by": "",
            }

            for k, v in defaults.items():
                if k in row:
                    row[k] = v

            append_rows_by_header("vendors", header, [row])

            bust_cache()

            st.success("新增成功")

            st.rerun()

        except Exception as e:

            st.error(f"新增失敗：{e}")

    st.divider()

    # --------------------------------------------------------
    # 廠商列表
    # --------------------------------------------------------

    st.subheader("廠商列表")

    vendors_df = vendors_df.copy()

    if "is_active" in vendors_df.columns:

        active_df = vendors_df[vendors_df["is_active"] == True]

    else:

        active_df = vendors_df

    if active_df.empty:

        st.info("目前沒有廠商")

        return

    show_cols = []

    if "vendor_id" in active_df.columns:
        show_cols.append("vendor_id")

    if "vendor_name" in active_df.columns:
        show_cols.append("vendor_name")

    st.dataframe(
        active_df[show_cols],
        use_container_width=True
    )

    st.divider()

    if st.button("⬅ 返回", use_container_width=True):

        st.session_state.step = "select_vendor"

        st.rerun()
