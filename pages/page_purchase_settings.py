"""
頁面模組：採購設定。
這一頁正式接上：
1. 廠商管理
2. 品項管理
3. 單位換算
4. 價格管理

設計原則：
- 先以「可維護、可直接使用」為主
- 不改動你既有主架構
- 資料來源可同時支援本機 Excel / Google 試算表
"""

from __future__ import annotations

from datetime import date
import pandas as pd
import streamlit as st

from oms_core import (
    _get_active_df,
    _item_display_name,
    _norm,
    _now_ts,
    _safe_float,
    allocate_ids,
    bust_cache,
    overwrite_table,
    read_table,
)


# ============================================================
# [P0] 共用小工具
# ============================================================
def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    work = df.copy() if df is not None else pd.DataFrame()
    for col in columns:
        if col not in work.columns:
            work[col] = ""
    return work


def _bool_text(v) -> str:
    text = str(v).strip().lower()
    return "true" if text in {"true", "1", "yes", "y", "是"} else "false"


def _active_options(df: pd.DataFrame, id_col: str, label_func) -> list[tuple[str, str]]:
    if df.empty:
        return []
    work = _get_active_df(df).copy()
    if work.empty:
        return []
    options = []
    for _, row in work.iterrows():
        item_id = _norm(row.get(id_col, ""))
        if not item_id:
            continue
        options.append((item_id, label_func(row)))
    return options


# ============================================================
# [P1] 廠商管理
# ============================================================
def _render_vendor_tab():
    st.subheader("廠商管理")

    vendors_df = _ensure_columns(read_table("vendors"), [
        "vendor_id", "brand_id", "vendor_code", "vendor_name", "vendor_name_zh",
        "contact_name", "phone", "line_id", "notes", "is_active", "created_at", "updated_at"
    ])

    show_active_only = st.toggle("只看啟用廠商", value=True, key="vendor_active_only")
    view_df = _get_active_df(vendors_df) if show_active_only else vendors_df.copy()

    if not view_df.empty:
        show_cols = [c for c in [
            "vendor_id", "vendor_name", "vendor_name_zh", "contact_name", "phone", "is_active", "updated_at"
        ] if c in view_df.columns]
        st.dataframe(view_df[show_cols], use_container_width=True, hide_index=True)
    else:
        st.info("目前沒有廠商資料。")

    st.markdown("---")
    st.markdown("#### 新增廠商")

    with st.form("form_add_vendor"):
        c1, c2 = st.columns(2)
        brand_id = c1.text_input("品牌 ID（可空白）", value="")
        vendor_name = c1.text_input("廠商名稱", value="")
        vendor_name_zh = c2.text_input("廠商中文名稱", value="")
        contact_name = c1.text_input("聯絡人", value="")
        phone = c2.text_input("電話", value="")
        vendor_code = c1.text_input("廠商代碼", value="")
        line_id = c2.text_input("LINE ID", value="")
        notes = st.text_area("備註", value="")
        is_active = st.toggle("啟用", value=True)
        submitted = st.form_submit_button("新增廠商", use_container_width=True)

    if submitted:
        if not vendor_name.strip() and not vendor_name_zh.strip():
            st.warning("廠商名稱不可空白。")
            return
        try:
            new_id = allocate_ids({"vendors": 1}).get("vendors", [""])[0]
            row = {c: "" for c in vendors_df.columns}
            row.update({
                "vendor_id": new_id,
                "brand_id": brand_id.strip(),
                "vendor_code": vendor_code.strip(),
                "vendor_name": vendor_name.strip(),
                "vendor_name_zh": vendor_name_zh.strip(),
                "contact_name": contact_name.strip(),
                "phone": phone.strip(),
                "line_id": line_id.strip(),
                "notes": notes.strip(),
                "is_active": _bool_text(is_active),
                "created_at": _now_ts(),
                "updated_at": _now_ts(),
            })
            vendors_df = pd.concat([vendors_df, pd.DataFrame([row])], ignore_index=True)
            overwrite_table("vendors", vendors_df)
            st.success(f"已新增廠商：{new_id}")
            st.rerun()
        except Exception as e:
            st.error(f"新增廠商失敗：{e}")

    st.markdown("---")
    st.markdown("#### 編輯 / 停用廠商")
    if vendors_df.empty:
        return

    vendor_map = {
        _norm(r.get("vendor_id", "")): f"{_norm(r.get('vendor_name','')) or _norm(r.get('vendor_name_zh','')) or _norm(r.get('vendor_id',''))}｜{_norm(r.get('vendor_id',''))}"
        for _, r in vendors_df.iterrows()
        if _norm(r.get("vendor_id", ""))
    }
    selected_vendor_id = st.selectbox("選擇廠商", options=list(vendor_map.keys()), format_func=lambda x: vendor_map.get(x, x), key="edit_vendor_id")
    target_idx = vendors_df[vendors_df["vendor_id"].astype(str).str.strip() == selected_vendor_id].index
    if len(target_idx) == 0:
        return
    idx = target_idx[0]
    row = vendors_df.loc[idx]

    with st.form("form_edit_vendor"):
        c1, c2 = st.columns(2)
        edit_vendor_name = c1.text_input("廠商名稱", value=_norm(row.get("vendor_name", "")))
        edit_vendor_name_zh = c2.text_input("廠商中文名稱", value=_norm(row.get("vendor_name_zh", "")))
        edit_contact_name = c1.text_input("聯絡人", value=_norm(row.get("contact_name", "")))
        edit_phone = c2.text_input("電話", value=_norm(row.get("phone", "")))
        edit_line = c1.text_input("LINE ID", value=_norm(row.get("line_id", "")))
        edit_notes = c2.text_input("備註", value=_norm(row.get("notes", "")))
        edit_active = st.toggle("啟用", value=str(row.get("is_active", "true")).strip().lower() in {"true", "1", "yes", "y", "是"})
        save_vendor = st.form_submit_button("儲存廠商變更", use_container_width=True)

    if save_vendor:
        vendors_df.loc[idx, "vendor_name"] = edit_vendor_name.strip()
        vendors_df.loc[idx, "vendor_name_zh"] = edit_vendor_name_zh.strip()
        vendors_df.loc[idx, "contact_name"] = edit_contact_name.strip()
        vendors_df.loc[idx, "phone"] = edit_phone.strip()
        vendors_df.loc[idx, "line_id"] = edit_line.strip()
        vendors_df.loc[idx, "notes"] = edit_notes.strip()
        vendors_df.loc[idx, "is_active"] = _bool_text(edit_active)
        vendors_df.loc[idx, "updated_at"] = _now_ts()
        overwrite_table("vendors", vendors_df)
        st.success("廠商資料已更新。")
        st.rerun()


# ============================================================
# [P2] 品項管理
# ============================================================
def _render_item_tab():
    st.subheader("品項管理")

    items_df = _ensure_columns(read_table("items"), [
        "item_id", "brand_id", "default_vendor_id", "item_name", "item_name_zh", "item_type",
        "base_unit", "default_stock_unit", "default_order_unit", "orderable_units", "is_active",
        "category", "spec", "created_at", "updated_at"
    ])
    vendors_df = read_table("vendors")
    units_df = read_table("units")

    show_active_only = st.toggle("只看啟用品項", value=True, key="item_active_only")
    view_df = _get_active_df(items_df) if show_active_only else items_df.copy()
    if not view_df.empty:
        show_cols = [c for c in [
            "item_id", "item_name_zh", "item_name", "default_vendor_id", "base_unit", "default_order_unit", "is_active"
        ] if c in view_df.columns]
        st.dataframe(view_df[show_cols], use_container_width=True, hide_index=True)
    else:
        st.info("目前沒有品項資料。")

    vendor_options = _active_options(vendors_df, "vendor_id", lambda r: _norm(r.get("vendor_name", "")) or _norm(r.get("vendor_name_zh", "")) or _norm(r.get("vendor_id", "")))
    vendor_ids = [x[0] for x in vendor_options]
    vendor_label_map = {x[0]: x[1] for x in vendor_options}

    unit_values = []
    if not units_df.empty:
        if "unit_symbol" in units_df.columns:
            unit_values.extend([_norm(x) for x in units_df["unit_symbol"].tolist()])
        if "unit_name_zh" in units_df.columns:
            unit_values.extend([_norm(x) for x in units_df["unit_name_zh"].tolist()])
        if "unit_name" in units_df.columns:
            unit_values.extend([_norm(x) for x in units_df["unit_name"].tolist()])
    unit_values = [x for x in dict.fromkeys(unit_values) if x]

    st.markdown("---")
    st.markdown("#### 新增品項")
    with st.form("form_add_item"):
        c1, c2 = st.columns(2)
        item_name = c1.text_input("品項名稱", value="")
        item_name_zh = c2.text_input("品項中文名稱", value="")
        default_vendor_id = c1.selectbox("預設廠商", options=[""] + vendor_ids, format_func=lambda x: vendor_label_map.get(x, x or "未指定"))
        item_type = c2.selectbox("品項類型", options=["ingredient", "product"], index=0)
        base_unit = c1.selectbox("基準單位", options=unit_values if unit_values else [""])
        stock_unit = c2.selectbox("庫存單位", options=unit_values if unit_values else [""])
        order_unit = c1.selectbox("叫貨單位", options=unit_values if unit_values else [""])
        orderable_units = c2.text_input("可叫貨單位（逗號分隔）", value="")
        category = c1.text_input("分類", value="")
        spec = c2.text_input("規格", value="")
        is_active = st.toggle("啟用", value=True, key="item_add_active")
        submit_item = st.form_submit_button("新增品項", use_container_width=True)

    if submit_item:
        if not item_name.strip() and not item_name_zh.strip():
            st.warning("品項名稱不可空白。")
            return
        try:
            new_id = allocate_ids({"items": 1}).get("items", [""])[0]
            row = {c: "" for c in items_df.columns}
            row.update({
                "item_id": new_id,
                "default_vendor_id": default_vendor_id,
                "item_name": item_name.strip(),
                "item_name_zh": item_name_zh.strip(),
                "item_type": item_type,
                "base_unit": base_unit,
                "default_stock_unit": stock_unit or base_unit,
                "default_order_unit": order_unit or base_unit,
                "orderable_units": orderable_units.strip(),
                "category": category.strip(),
                "spec": spec.strip(),
                "is_active": _bool_text(is_active),
                "created_at": _now_ts(),
                "updated_at": _now_ts(),
            })
            items_df = pd.concat([items_df, pd.DataFrame([row])], ignore_index=True)
            overwrite_table("items", items_df)
            st.success(f"已新增品項：{new_id}")
            st.rerun()
        except Exception as e:
            st.error(f"新增品項失敗：{e}")

    st.markdown("---")
    st.markdown("#### 編輯品項")
    if items_df.empty:
        return
    item_options = {
        _norm(r.get("item_id", "")): f"{_item_display_name(r) or _norm(r.get('item_id',''))}｜{_norm(r.get('item_id',''))}"
        for _, r in items_df.iterrows() if _norm(r.get("item_id", ""))
    }
    selected_item_id = st.selectbox("選擇品項", options=list(item_options.keys()), format_func=lambda x: item_options.get(x, x), key="edit_item_id")
    hit_idx = items_df[items_df["item_id"].astype(str).str.strip() == selected_item_id].index
    if len(hit_idx) == 0:
        return
    idx = hit_idx[0]
    row = items_df.loc[idx]

    with st.form("form_edit_item"):
        c1, c2 = st.columns(2)
        edit_item_name = c1.text_input("品項名稱", value=_norm(row.get("item_name", "")))
        edit_item_name_zh = c2.text_input("品項中文名稱", value=_norm(row.get("item_name_zh", "")))
        default_vendor_default = _norm(row.get("default_vendor_id", ""))
        if default_vendor_default not in [""] + vendor_ids:
            vendor_ids = vendor_ids + [default_vendor_default]
        edit_vendor = c1.selectbox("預設廠商", options=[""] + vendor_ids, index=([""] + vendor_ids).index(default_vendor_default), format_func=lambda x: vendor_label_map.get(x, x or "未指定"))
        item_type_default = _norm(row.get("item_type", "ingredient")) or "ingredient"
        type_options = ["ingredient", "product"]
        if item_type_default not in type_options:
            type_options.append(item_type_default)
        edit_type = c2.selectbox("品項類型", options=type_options, index=type_options.index(item_type_default))
        base_default = _norm(row.get("base_unit", ""))
        stock_default = _norm(row.get("default_stock_unit", ""))
        order_default = _norm(row.get("default_order_unit", ""))
        unit_opts = unit_values.copy() if unit_values else [""]
        for extra in [base_default, stock_default, order_default]:
            if extra and extra not in unit_opts:
                unit_opts.append(extra)
        edit_base = c1.selectbox("基準單位", options=unit_opts, index=unit_opts.index(base_default) if base_default in unit_opts else 0)
        edit_stock = c2.selectbox("庫存單位", options=unit_opts, index=unit_opts.index(stock_default) if stock_default in unit_opts else 0)
        edit_order = c1.selectbox("叫貨單位", options=unit_opts, index=unit_opts.index(order_default) if order_default in unit_opts else 0)
        edit_orderable = c2.text_input("可叫貨單位（逗號分隔）", value=_norm(row.get("orderable_units", "")))
        edit_category = c1.text_input("分類", value=_norm(row.get("category", "")))
        edit_spec = c2.text_input("規格", value=_norm(row.get("spec", "")))
        edit_active = st.toggle("啟用", value=str(row.get("is_active", "true")).strip().lower() in {"true", "1", "yes", "y", "是"}, key="item_edit_active")
        save_item = st.form_submit_button("儲存品項變更", use_container_width=True)

    if save_item:
        items_df.loc[idx, "item_name"] = edit_item_name.strip()
        items_df.loc[idx, "item_name_zh"] = edit_item_name_zh.strip()
        items_df.loc[idx, "default_vendor_id"] = edit_vendor
        items_df.loc[idx, "item_type"] = edit_type
        items_df.loc[idx, "base_unit"] = edit_base
        items_df.loc[idx, "default_stock_unit"] = edit_stock
        items_df.loc[idx, "default_order_unit"] = edit_order
        items_df.loc[idx, "orderable_units"] = edit_orderable.strip()
        items_df.loc[idx, "category"] = edit_category.strip()
        items_df.loc[idx, "spec"] = edit_spec.strip()
        items_df.loc[idx, "is_active"] = _bool_text(edit_active)
        items_df.loc[idx, "updated_at"] = _now_ts()
        overwrite_table("items", items_df)
        st.success("品項資料已更新。")
        st.rerun()


# ============================================================
# [P3] 單位換算管理
# ============================================================
def _render_conversion_tab():
    st.subheader("單位換算")

    conv_df = _ensure_columns(read_table("unit_conversions"), [
        "conversion_id", "item_id", "from_unit", "to_unit", "ratio", "is_active", "created_at", "updated_at"
    ])
    items_df = read_table("items")

    if not conv_df.empty:
        st.dataframe(conv_df[[c for c in ["conversion_id", "item_id", "from_unit", "to_unit", "ratio", "is_active"] if c in conv_df.columns]], use_container_width=True, hide_index=True)
    else:
        st.info("目前沒有單位換算資料。")

    item_options = {}
    if not items_df.empty:
        item_options = {
            _norm(r.get("item_id", "")): f"{_item_display_name(r) or _norm(r.get('item_id',''))}｜{_norm(r.get('item_id',''))}"
            for _, r in items_df.iterrows() if _norm(r.get("item_id", ""))
        }

    st.markdown("---")
    with st.form("form_add_conversion"):
        item_id = st.selectbox("品項", options=list(item_options.keys()), format_func=lambda x: item_options.get(x, x)) if item_options else st.text_input("品項 ID")
        c1, c2 = st.columns(2)
        from_unit = c1.text_input("from_unit", value="")
        to_unit = c2.text_input("to_unit", value="")
        ratio = st.number_input("ratio", min_value=0.0, value=1.0, step=0.1)
        is_active = st.toggle("啟用", value=True, key="conv_active")
        submit_conv = st.form_submit_button("新增換算", use_container_width=True)

    if submit_conv:
        if not _norm(item_id) or not from_unit.strip() or not to_unit.strip() or ratio <= 0:
            st.warning("品項 / 單位 / ratio 都要正確填寫。")
            return
        try:
            new_id = allocate_ids({"unit_conversions": 1}).get("unit_conversions", [""])
            conv_id = new_id[0] if new_id else f"CONV_{len(conv_df)+1:06d}"
            row = {c: "" for c in conv_df.columns}
            row.update({
                "conversion_id": conv_id,
                "item_id": _norm(item_id),
                "from_unit": from_unit.strip(),
                "to_unit": to_unit.strip(),
                "ratio": str(ratio),
                "is_active": _bool_text(is_active),
                "created_at": _now_ts(),
                "updated_at": _now_ts(),
            })
            conv_df = pd.concat([conv_df, pd.DataFrame([row])], ignore_index=True)
            overwrite_table("unit_conversions", conv_df)
            st.success(f"已新增換算：{conv_id}")
            st.rerun()
        except Exception as e:
            st.error(f"新增換算失敗：{e}")


# ============================================================
# [P4] 價格管理
# ============================================================
def _render_price_tab():
    st.subheader("價格管理")

    prices_df = _ensure_columns(read_table("prices"), [
        "price_id", "item_id", "unit_price", "price_unit", "effective_date", "end_date", "is_active", "created_at", "updated_at"
    ])
    items_df = read_table("items")

    if not prices_df.empty:
        work = prices_df.copy()
        st.dataframe(work[[c for c in ["price_id", "item_id", "unit_price", "price_unit", "effective_date", "end_date", "is_active"] if c in work.columns]], use_container_width=True, hide_index=True)
    else:
        st.info("目前沒有價格資料。")

    item_options = {}
    if not items_df.empty:
        item_options = {
            _norm(r.get("item_id", "")): f"{_item_display_name(r) or _norm(r.get('item_id',''))}｜{_norm(r.get('item_id',''))}"
            for _, r in items_df.iterrows() if _norm(r.get("item_id", ""))
        }

    st.markdown("---")
    with st.form("form_add_price"):
        item_id = st.selectbox("品項", options=list(item_options.keys()), format_func=lambda x: item_options.get(x, x)) if item_options else st.text_input("品項 ID")
        c1, c2 = st.columns(2)
        unit_price = c1.number_input("單價", min_value=0.0, value=0.0, step=1.0)
        price_unit = c2.text_input("價格單位", value="")
        effective_date = c1.date_input("生效日", value=date.today())
        end_date = c2.date_input("結束日（可不填）", value=None)
        is_active = st.toggle("啟用", value=True, key="price_active")
        submit_price = st.form_submit_button("新增價格", use_container_width=True)

    if submit_price:
        if not _norm(item_id) or unit_price < 0:
            st.warning("品項與價格需正確填寫。")
            return
        try:
            new_id = allocate_ids({"prices": 1}).get("prices", [""])[0]
            row = {c: "" for c in prices_df.columns}
            row.update({
                "price_id": new_id,
                "item_id": _norm(item_id),
                "unit_price": str(unit_price),
                "price_unit": price_unit.strip(),
                "effective_date": str(effective_date),
                "end_date": str(end_date) if end_date else "",
                "is_active": _bool_text(is_active),
                "created_at": _now_ts(),
                "updated_at": _now_ts(),
            })
            prices_df = pd.concat([prices_df, pd.DataFrame([row])], ignore_index=True)
            overwrite_table("prices", prices_df)
            st.success(f"已新增價格：{new_id}")
            st.rerun()
        except Exception as e:
            st.error(f"新增價格失敗：{e}")


# ============================================================
# [E5] 採購設定頁主入口
# ============================================================
def page_purchase_settings():
    st.title("🛒 採購設定")
    st.caption("此頁已接上資料維護，可同時支援本機 Excel / Google 試算表。")

    tab1, tab2, tab3, tab4 = st.tabs(["廠商管理", "品項管理", "單位換算", "價格管理"])

    with tab1:
        _render_vendor_tab()
    with tab2:
        _render_item_tab()
    with tab3:
        _render_conversion_tab()
    with tab4:
        _render_price_tab()
