from __future__ import annotations

import streamlit as st

from users_permissions.services.service_stores import create_store, update_store_active


from users_permissions.services.service_stores import (
    StoreServiceError,
    build_brand_options,
    build_store_admin_view,
    generate_next_store_code,
    load_store_admin_tables,
)


def ensure_store_admin_access(role_id: str):
    if str(role_id or "").strip().lower() not in ["owner", "admin"]:
        raise StoreServiceError("你沒有權限進入此頁。")


def build_store_admin_page_data():
    stores_df, brands_df = load_store_admin_tables()
    stores_view, brand_label_col = build_store_admin_view(stores_df, brands_df)
    brand_options, brand_label_map = build_brand_options(brands_df, brand_label_col)
    preview_store_code = generate_next_store_code(stores_df)
    return {
        "stores_df": stores_df,
        "brands_df": brands_df,
        "stores_view": stores_view,
        "brand_label_col": brand_label_col,
        "brand_options": brand_options,
        "brand_label_map": brand_label_map,
        "preview_store_code": preview_store_code,
    }


def submit_create_store(*, brand_id: str, store_name_zh: str):
    return create_store(
        brand_id=brand_id,
        store_name_zh=store_name_zh,
        actor=st.session_state.get("login_user", "system"),
    )


def submit_update_store_active(*, store_id: str, new_active: int):
    return update_store_active(
        store_id=store_id,
        new_active=new_active,
        actor=st.session_state.get("login_user", "system"),
    )



def build_store_list_display_df(stores_view):
    if stores_view is None or stores_view.empty:
        return stores_view
    show_df = stores_view[["store_display", "brand_display", "status_text"]].copy()
    show_df.columns = ["分店名稱", "品牌", "狀態"]
    return show_df


def build_store_toggle_state(stores_view):
    option_map = {}
    if stores_view is not None and not stores_view.empty:
        for _, row in stores_view.iterrows():
            sid = str(row.get("store_id", "")).strip()
            sname = str(row.get("store_display", "")).strip()
            status_text = str(row.get("status_text", "")).strip()
            option_map[sid] = f"{sname}（{status_text}）"
    store_ids = list(option_map.keys())
    selected_store_id = store_ids[0] if store_ids else ""
    current_active = 1
    if selected_store_id and stores_view is not None and not stores_view.empty:
        current_row = stores_view[stores_view["store_id"] == selected_store_id].copy()
        if not current_row.empty:
            current_active = int(current_row.iloc[0]["is_active"])
    return {"option_map": option_map, "store_ids": store_ids, "selected_store_id": selected_store_id, "current_active": current_active}


def resolve_store_toggle_state(stores_view, selected_store_id: str):
    option_map = {}
    if stores_view is not None and not stores_view.empty:
        for _, row in stores_view.iterrows():
            sid = str(row.get("store_id", "")).strip()
            sname = str(row.get("store_display", "")).strip()
            status_text = str(row.get("status_text", "")).strip()
            option_map[sid] = f"{sname}（{status_text}）"
    store_ids = list(option_map.keys())
    resolved_store_id = selected_store_id if selected_store_id in store_ids else (store_ids[0] if store_ids else "")
    current_active = 1
    if resolved_store_id and stores_view is not None and not stores_view.empty:
        current_row = stores_view[stores_view["store_id"] == resolved_store_id].copy()
        if not current_row.empty:
            current_active = int(current_row.iloc[0]["is_active"])
    return {"option_map": option_map, "store_ids": store_ids, "selected_store_id": resolved_store_id, "current_active": current_active}
