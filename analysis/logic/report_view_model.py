from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from shared.services.service_reports import (
    build_inventory_history_summary_df,
    build_latest_item_metrics_df,
    build_purchase_detail_df,
    clean_option_list,
    get_active_df,
    get_base_unit_cost,
    item_display_name,
    norm,
    safe_float,
)
from shared.services.service_sheet import sheet_get_versions
from shared.utils.utils_format import unit_label
from shared.utils.utils_units import convert_unit, get_base_unit


ALL_VENDORS = "全部廠商"
ALL_ITEMS = "全部品項"
DISPLAY_MODE_MOBILE = "手機精簡"
DISPLAY_MODE_FULL = "完整報表"


def _build_history_vendor_enriched_df(store_id: str, start_date: date, end_date: date, shared_tables: dict[str, pd.DataFrame]):
    hist_df = build_inventory_history_summary_df(store_id=store_id, start_date=start_date, end_date=end_date)
    if hist_df.empty:
        return hist_df
    if "廠商" in hist_df.columns and hist_df["廠商"].astype(str).str.strip().ne("").any():
        return hist_df
    items_df = shared_tables["items"]
    vendors_df = shared_tables["vendors"]
    if items_df.empty or vendors_df.empty:
        hist_df["廠商"] = "-"
        return hist_df
    items_map = items_df.copy()
    vendors_map = vendors_df.copy()
    if "item_id" not in items_map.columns or "default_vendor_id" not in items_map.columns:
        hist_df["廠商"] = "-"
        return hist_df
    if "vendor_id" not in vendors_map.columns:
        hist_df["廠商"] = "-"
        return hist_df
    items_map["item_id"] = items_map["item_id"].astype(str).str.strip()
    items_map["default_vendor_id"] = items_map["default_vendor_id"].astype(str).str.strip()
    items_map = items_map[["item_id", "default_vendor_id"]].drop_duplicates()
    vendors_map["vendor_id"] = vendors_map["vendor_id"].astype(str).str.strip()
    vendors_map["廠商"] = vendors_map.apply(lambda r: norm(r.get("vendor_name", "")) or norm(r.get("vendor_id", "")) or "-", axis=1)
    vendors_map = vendors_map[["vendor_id", "廠商"]].drop_duplicates()
    merged = hist_df.merge(items_map, on="item_id", how="left")
    merged = merged.merge(vendors_map, left_on="default_vendor_id", right_on="vendor_id", how="left")
    merged["廠商"] = merged["廠商"].fillna("-")
    for col in ["default_vendor_id", "vendor_id"]:
        if col in merged.columns:
            merged = merged.drop(columns=[col])
    return merged


def build_history_with_vendor(store_id: str, start_date: date, end_date: date, shared_tables: dict[str, pd.DataFrame]):
    return _build_history_vendor_enriched_df(store_id=store_id, start_date=start_date, end_date=end_date, shared_tables=shared_tables)


def build_analysis_with_vendor(store_id: str, start_date: date, end_date: date, shared_tables: dict[str, pd.DataFrame]):
    return _build_history_vendor_enriched_df(store_id=store_id, start_date=start_date, end_date=end_date, shared_tables=shared_tables)


def _build_purchase_filtered_df(store_id: str, start_date: date, end_date: date):
    po_detail_df = build_purchase_detail_df()
    if po_detail_df.empty:
        return pd.DataFrame()
    date_field = "operation_date_dt" if "operation_date_dt" in po_detail_df.columns else "order_date_dt"
    purchase_mask = (
        po_detail_df["store_id"].astype(str).str.strip().eq(str(store_id).strip())
        & po_detail_df[date_field].notna()
        & po_detail_df[date_field].ge(start_date)
        & po_detail_df[date_field].le(end_date)
    )
    if not purchase_mask.any():
        return pd.DataFrame()
    purchase_filt = po_detail_df.loc[purchase_mask].copy()
    purchase_filt["日期"] = pd.to_datetime(purchase_filt[date_field], errors="coerce").dt.strftime("%m/%d")
    purchase_filt["廠商"] = purchase_filt["vendor_name_disp"].map(lambda x: norm(x) or "-")
    purchase_filt["進貨金額"] = pd.to_numeric(purchase_filt["amount_num"], errors="coerce").fillna(0)
    return purchase_filt


def _build_vendor_item_option_maps(shared_tables: dict[str, pd.DataFrame]):
    items_df = shared_tables["items"].copy()
    vendors_df = shared_tables["vendors"].copy()
    if items_df.empty:
        return {ALL_VENDORS: []}
    items_df.columns = [str(c).strip() for c in items_df.columns]
    items_df["item_id"] = items_df.get("item_id", "").astype(str).str.strip()
    items_df["default_vendor_id"] = items_df.get("default_vendor_id", "").astype(str).str.strip()
    items_df["品項顯示"] = items_df.apply(lambda r: norm(r.get("item_name_zh", "")) or norm(r.get("item_name", "")) or norm(r.get("item_id", "")), axis=1)
    if "is_active" in items_df.columns:
        items_df = items_df[items_df["is_active"].astype(str).str.strip().isin(["1", "True", "true", "YES", "yes", "是"])].copy()
    all_items = clean_option_list(items_df["品項顯示"].dropna().tolist()) if not items_df.empty else []
    option_map = {ALL_VENDORS: all_items}
    if vendors_df.empty:
        return option_map
    vendors_df.columns = [str(c).strip() for c in vendors_df.columns]
    vendors_df["vendor_id"] = vendors_df.get("vendor_id", "").astype(str).str.strip()
    vendors_df["vendor_namenorm"] = vendors_df.apply(lambda r: norm(r.get("vendor_name", "")) or norm(r.get("vendor_id", "")), axis=1)
    for row in vendors_df.itertuples(index=False):
        vendor_id = str(getattr(row, "vendor_id", "") or "").strip()
        vendor_name = str(getattr(row, "vendor_namenorm", "") or "").strip()
        if not vendor_name:
            continue
        vendor_items = items_df[items_df["default_vendor_id"].astype(str).str.strip() == vendor_id].copy()
        option_map[vendor_name] = clean_option_list(vendor_items["品項顯示"].dropna().tolist()) if not vendor_items.empty else []
    return option_map


def _build_nonzero_detail_df(hist_df: pd.DataFrame):
    if hist_df.empty:
        return pd.DataFrame()
    detail_df = hist_df.copy()
    return detail_df[
        (detail_df["上次庫存"] != 0)
        | (detail_df["期間進貨"] != 0)
        | (detail_df["期間消耗"] != 0)
        | (detail_df["這次庫存"] != 0)
        | (detail_df.get("這次叫貨", 0) != 0)
    ].copy()


def _build_vendor_summary_df(purchase_filt: pd.DataFrame):
    if purchase_filt.empty:
        return pd.DataFrame()
    vendor_summary = purchase_filt.groupby(["日期", "廠商"], as_index=False)["進貨金額"].sum()
    return vendor_summary.sort_values(["日期", "廠商"], ascending=[False, True]).reset_index(drop=True)


def _build_report_detail_frames(*, detail_df: pd.DataFrame, selected_vendor: str, display_mode: str, date_col: str, full_cols: list[str]):
    export_df = pd.DataFrame()
    show_df = pd.DataFrame()
    if detail_df.empty or selected_vendor == ALL_VENDORS:
        return export_df, show_df
    export_df = detail_df[full_cols].copy().reset_index(drop=True)
    export_df = format_mmdd_column(export_df, date_col)
    if display_mode == DISPLAY_MODE_MOBILE:
        show_df = export_df[[date_col, "品項", "這次庫存", "這次叫貨", "日平均"]].copy()
        show_df["品項"] = show_df["品項"].apply(short_item_name)
    else:
        show_df = export_df.copy()
    return export_df, show_df


def _build_history_analysis_shared_upstream(store_id: str, start_date: date, end_date: date, shared_tables: dict[str, pd.DataFrame]):
    signature = (
        str(store_id).strip(),
        str(start_date),
        str(end_date),
        sheet_get_versions(("stocktakes", "stocktake_lines", "purchase_orders", "purchase_order_lines", "items", "vendors")),
    )
    cache = st.session_state.get("_history_analysis_upstream_cache")
    if isinstance(cache, dict) and cache.get("signature") == signature:
        data = cache.get("data", {})
        return {
            "hist_df": data.get("hist_df", pd.DataFrame()).copy(),
            "purchase_filt": data.get("purchase_filt", pd.DataFrame()).copy(),
            "vendor_options": list(data.get("vendor_options", [ALL_VENDORS])),
            "vendor_item_option_map": {k: list(v) for k, v in data.get("vendor_item_option_map", {}).items()},
            "base_detail_df": data.get("base_detail_df", pd.DataFrame()).copy(),
            "vendor_summary": data.get("vendor_summary", pd.DataFrame()).copy(),
        }

    hist_df = _build_history_vendor_enriched_df(store_id=store_id, start_date=start_date, end_date=end_date, shared_tables=shared_tables)
    purchase_filt = _build_purchase_filtered_df(store_id=store_id, start_date=start_date, end_date=end_date)
    if not hist_df.empty and "廠商" in hist_df.columns:
        vendor_values = clean_option_list(hist_df["廠商"].dropna().tolist())
    elif not purchase_filt.empty and "廠商" in purchase_filt.columns:
        vendor_values = clean_option_list(purchase_filt["廠商"].dropna().tolist())
    else:
        vendor_values = []
    vendor_options = [ALL_VENDORS] + vendor_values
    vendor_item_option_map = _build_vendor_item_option_maps(shared_tables)
    base_detail_df = _build_nonzero_detail_df(hist_df)
    vendor_summary = _build_vendor_summary_df(purchase_filt)
    data = {
        "hist_df": hist_df.copy(),
        "purchase_filt": purchase_filt.copy(),
        "vendor_options": list(vendor_options),
        "vendor_item_option_map": {k: list(v) for k, v in vendor_item_option_map.items()},
        "base_detail_df": base_detail_df.copy(),
        "vendor_summary": vendor_summary.copy(),
    }
    st.session_state["_history_analysis_upstream_cache"] = {"signature": signature, "data": data}
    return {
        "hist_df": hist_df,
        "purchase_filt": purchase_filt,
        "vendor_options": vendor_options,
        "vendor_item_option_map": vendor_item_option_map,
        "base_detail_df": base_detail_df,
        "vendor_summary": vendor_summary,
    }


def short_item_name(text: str, max_len: int = 14) -> str:
    value = str(text or "").strip()
    return value if len(value) <= max_len else value[:max_len] + ".."


def format_mmdd_value(value):
    dt = pd.to_datetime(value, errors="coerce")
    return value if pd.isna(dt) else dt.strftime("%m/%d")


def format_mmdd_column(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if df.empty or col not in df.columns:
        return df
    out = df.copy()
    out[col] = out[col].apply(format_mmdd_value)
    return out


def convert_compare_qty_to_display_unit(*, qty: float, item_id: str, target_unit: str, items_df: pd.DataFrame, conversions_df: pd.DataFrame, as_of_date: date) -> float:
    qty = safe_float(qty, 0)
    item_id = norm(item_id)
    target_unit = norm(target_unit)
    if qty == 0 or not item_id or not target_unit:
        return round(qty, 1)
    try:
        base_unit = get_base_unit(items_df, item_id)
        if target_unit == base_unit:
            return round(qty, 1)
        converted = convert_unit(item_id=item_id, qty=qty, from_unit=base_unit, to_unit=target_unit, conversions_df=conversions_df, as_of_date=as_of_date)
        return round(converted, 1)
    except Exception:
        return round(qty, 1)


def get_store_scope_options(shared_tables: dict[str, pd.DataFrame], current_store_id: str, current_store_name: str, login_role: str):
    stores_df = shared_tables["stores"]
    if stores_df.empty or "store_id" not in stores_df.columns:
        return ([current_store_id] if current_store_id else [], {current_store_id: current_store_name} if current_store_id else {})
    stores_df = stores_df.copy()
    stores_df["store_id"] = stores_df["store_id"].astype(str).str.strip()
    if "store_name_zh" not in stores_df.columns:
        stores_df["store_name_zh"] = ""
    if "store_name" not in stores_df.columns:
        stores_df["store_name"] = stores_df["store_id"]
    if "is_active" in stores_df.columns:
        stores_df = stores_df[stores_df["is_active"].apply(lambda x: str(x).strip() in ["1", "True", "TRUE", "true", "1.0"])].copy()
    stores_df["store_display"] = stores_df["store_name_zh"].astype(str).str.strip()
    stores_df.loc[stores_df["store_display"] == "", "store_display"] = stores_df["store_name"].astype(str).str.strip()
    work = stores_df.sort_values([c for c in ["store_name_zh", "store_name", "store_id"] if c in stores_df.columns]).copy() if login_role in ["owner", "admin"] else stores_df[stores_df["store_id"] == current_store_id].copy()
    if work.empty and current_store_id:
        return [current_store_id], {current_store_id: current_store_name or current_store_id}
    option_map = dict(zip(work["store_id"].tolist(), work["store_display"].tolist()))
    return list(option_map.keys()), option_map


def build_stock_order_compare_view_model(store_id: str, selected_date: date, selected_vendor: str, shared_tables: dict[str, pd.DataFrame]):
    compare_signature = (
        str(store_id).strip(),
        str(selected_date),
        sheet_get_versions(("stocktakes", "stocktake_lines", "purchase_orders", "purchase_order_lines", "items", "vendors", "stores", "unit_conversions")),
    )
    cache = st.session_state.get("_stock_order_compare_vm_cache")
    if isinstance(cache, dict) and cache.get("signature") == compare_signature:
        preview_all = cache.get("preview_all", pd.DataFrame())
        vendor_options = list(cache.get("vendor_options", [ALL_VENDORS]))
        has_source = bool(cache.get("has_source", False))
        if selected_vendor != ALL_VENDORS and not preview_all.empty and "廠商" in preview_all.columns:
            preview = preview_all[preview_all["廠商"].astype(str).str.strip() == str(selected_vendor).strip()].reset_index(drop=True)
        else:
            preview = preview_all.copy()
        return {"preview": preview, "vendor_options": vendor_options, "has_source": has_source}

    latest_df = build_latest_item_metrics_df(store_id=store_id, as_of_date=selected_date)
    if latest_df.empty:
        result = {"preview": pd.DataFrame(), "vendor_options": [ALL_VENDORS], "has_source": False}
        st.session_state["_stock_order_compare_vm_cache"] = {"signature": compare_signature, "preview_all": pd.DataFrame(), "vendor_options": [ALL_VENDORS], "has_source": False}
        return result

    work = latest_df.copy()
    if "日期_dt" in work.columns:
        work = work[pd.to_datetime(work["日期_dt"], errors="coerce").dt.date == selected_date].copy()
    elif "日期" in work.columns:
        work = work[pd.to_datetime(work["日期"], errors="coerce").dt.date == selected_date].copy()
    if work.empty:
        result = {"preview": pd.DataFrame(), "vendor_options": [ALL_VENDORS], "has_source": True}
        st.session_state["_stock_order_compare_vm_cache"] = {"signature": compare_signature, "preview_all": pd.DataFrame(), "vendor_options": [ALL_VENDORS], "has_source": True}
        return result

    if "這次庫存" not in work.columns:
        work["這次庫存"] = 0
    if "這次叫貨" not in work.columns:
        work["這次叫貨"] = 0
    work["這次庫存"] = pd.to_numeric(work["這次庫存"], errors="coerce").fillna(0.0)
    work["這次叫貨"] = pd.to_numeric(work["這次叫貨"], errors="coerce").fillna(0.0)
    work = work[(work["這次庫存"] != 0) | (work["這次叫貨"] != 0)].copy()
    if work.empty:
        result = {"preview": pd.DataFrame(), "vendor_options": [ALL_VENDORS], "has_source": True}
        st.session_state["_stock_order_compare_vm_cache"] = {"signature": compare_signature, "preview_all": pd.DataFrame(), "vendor_options": [ALL_VENDORS], "has_source": True}
        return result

    items_df = shared_tables["items"]
    vendors_df = shared_tables["vendors"]
    conversions_df = get_active_df(shared_tables["unit_conversions"])

    item_id_series = work.get("item_id", pd.Series("", index=work.index)).astype(str).str.strip()
    work["item_id"] = item_id_series

    stock_unit_map = {}
    order_unit_map = {}
    base_unit_map = {}
    item_vendor_map = {}
    if not items_df.empty and "item_id" in items_df.columns:
        items_work = items_df.copy()
        items_work["item_id"] = items_work["item_id"].astype(str).str.strip()
        if "default_stock_unit" in items_work.columns:
            stock_unit_map = dict(zip(items_work["item_id"], items_work["default_stock_unit"].astype(str).str.strip()))
        if "default_order_unit" in items_work.columns:
            order_unit_map = dict(zip(items_work["item_id"], items_work["default_order_unit"].astype(str).str.strip()))
        if "base_unit" in items_work.columns:
            base_unit_map = dict(zip(items_work["item_id"], items_work["base_unit"].astype(str).str.strip()))
        if "default_vendor_id" in items_work.columns:
            item_vendor_map = dict(zip(items_work["item_id"], items_work["default_vendor_id"].astype(str).str.strip()))

    vendor_map = {}
    if not vendors_df.empty and "vendor_id" in vendors_df.columns:
        vendors_work = vendors_df.copy()
        vendors_work["vendor_id"] = vendors_work["vendor_id"].astype(str).str.strip()
        vendors_work["vendor_name_disp"] = vendors_work.get("vendor_name_zh", "").astype(str).str.strip()
        if "vendor_name" in vendors_work.columns:
            fallback_vendor_name = vendors_work["vendor_name"].astype(str).str.strip()
            vendors_work.loc[vendors_work["vendor_name_disp"] == "", "vendor_name_disp"] = fallback_vendor_name
        vendors_work.loc[vendors_work["vendor_name_disp"] == "", "vendor_name_disp"] = vendors_work["vendor_id"]
        vendors_work.loc[vendors_work["vendor_name_disp"] == "", "vendor_name_disp"] = "-"
        vendor_map = dict(zip(vendors_work["vendor_id"], vendors_work["vendor_name_disp"]))

    if "vendor_id" in work.columns:
        vendor_id_series = work["vendor_id"].astype(str).str.strip()
    elif item_vendor_map:
        vendor_id_series = item_id_series.map(item_vendor_map).fillna("").astype(str).str.strip()
    else:
        vendor_id_series = pd.Series("", index=work.index, dtype="object")
    work["廠商"] = vendor_id_series.map(vendor_map).fillna("-") if vendor_map else "-"

    work["庫存顯示單位"] = item_id_series.map(stock_unit_map).fillna("")
    work["叫貨顯示單位"] = item_id_series.map(order_unit_map).fillna("")

    factor_cache: dict[tuple[str, str, str, str], float | None] = {}

    def _convert_display_values(qty_series: pd.Series, target_unit_series: pd.Series) -> list[float]:
        out: list[float] = []
        for item_id, qty, target_unit in zip(item_id_series.tolist(), qty_series.tolist(), target_unit_series.tolist()):
            qty_num = safe_float(qty, 0)
            item_key = norm(item_id)
            target_unit_key = norm(target_unit)
            if qty_num == 0 or not item_key or not target_unit_key:
                out.append(round(qty_num, 1))
                continue
            base_unit = norm(base_unit_map.get(item_key, ""))
            if not base_unit or target_unit_key == base_unit:
                out.append(round(qty_num, 1))
                continue
            factor_key = (item_key, base_unit, target_unit_key, str(selected_date))
            factor = factor_cache.get(factor_key)
            if factor_key not in factor_cache:
                try:
                    factor = convert_unit(
                        item_id=item_key,
                        qty=1.0,
                        from_unit=base_unit,
                        to_unit=target_unit_key,
                        conversions_df=conversions_df,
                        as_of_date=selected_date,
                    )
                except Exception:
                    factor = None
                factor_cache[factor_key] = factor
            if factor is None:
                out.append(round(qty_num, 1))
            else:
                out.append(round(qty_num * factor, 1))
        return out

    work["這次庫存_顯示值"] = _convert_display_values(work["這次庫存"], work["庫存顯示單位"])
    work["這次叫貨_顯示值"] = _convert_display_values(work["這次叫貨"], work["叫貨顯示單位"])

    item_col = "品項" if "品項" in work.columns else "item_id"
    preview_all = work[["廠商", item_col, "這次庫存_顯示值", "庫存顯示單位", "這次叫貨_顯示值", "叫貨顯示單位"]].copy()
    preview_all = preview_all.rename(columns={item_col: "品項", "這次庫存_顯示值": "這次庫存", "這次叫貨_顯示值": "這次叫貨"})
    preview_all["這次庫存"] = preview_all["這次庫存"].map(lambda v: f"{safe_float(v):g}") + preview_all["庫存顯示單位"].map(lambda v: f" {unit_label(str(v).strip())}" if str(v).strip() else "")
    preview_all["這次叫貨"] = preview_all["這次叫貨"].map(lambda v: f"{safe_float(v):g}") + preview_all["叫貨顯示單位"].map(lambda v: f" {unit_label(str(v).strip())}" if str(v).strip() else "")
    preview_all = preview_all.drop(columns=["庫存顯示單位", "叫貨顯示單位"]).sort_values(["廠商", "品項"], ascending=[True, True]).reset_index(drop=True)
    vendor_options = [ALL_VENDORS] + clean_option_list(preview_all["廠商"].dropna().tolist())

    st.session_state["_stock_order_compare_vm_cache"] = {
        "signature": compare_signature,
        "preview_all": preview_all.copy(),
        "vendor_options": list(vendor_options),
        "has_source": True,
    }

    if selected_vendor != ALL_VENDORS:
        preview = preview_all[preview_all["廠商"].astype(str).str.strip() == str(selected_vendor).strip()].reset_index(drop=True)
    else:
        preview = preview_all.copy()
    return {"preview": preview, "vendor_options": vendor_options, "has_source": True}

def build_history_page_view_model(store_id: str, start_date: date, end_date: date, selected_vendor: str, selected_item: str, display_mode: str, shared_tables: dict[str, pd.DataFrame]):
    upstream = _build_history_analysis_shared_upstream(store_id=store_id, start_date=start_date, end_date=end_date, shared_tables=shared_tables)
    hist_df = upstream["hist_df"]
    if hist_df.empty:
        return {"hist_df": hist_df, "vendor_options": [ALL_VENDORS], "item_options": [ALL_ITEMS], "detail_df": pd.DataFrame(), "export_df": pd.DataFrame(), "show_df": pd.DataFrame()}
    vendor_options = upstream["vendor_options"]
    item_values = upstream["vendor_item_option_map"].get(selected_vendor, upstream["vendor_item_option_map"].get(ALL_VENDORS, []))
    item_options = [ALL_ITEMS] + item_values
    detail_df = upstream["base_detail_df"]
    if selected_vendor != ALL_VENDORS:
        detail_df = detail_df[detail_df["廠商"].astype(str).str.strip() == str(selected_vendor).strip()].copy()
    if selected_item != ALL_ITEMS:
        detail_df = detail_df[detail_df["品項"].astype(str).str.strip() == str(selected_item).strip()].copy()
    export_df, show_df = _build_report_detail_frames(
        detail_df=detail_df,
        selected_vendor=selected_vendor,
        display_mode=display_mode,
        date_col="日期顯示",
        full_cols=["日期顯示", "品項", "上次庫存", "期間進貨", "庫存合計", "這次庫存", "期間消耗", "這次叫貨", "日平均"],
    )
    return {"hist_df": hist_df, "vendor_options": vendor_options, "item_options": item_options, "detail_df": detail_df, "export_df": export_df, "show_df": show_df}


def build_export_view_model(export_type: str, selected_store_id: str, selected_store_name: str, start: date, end: date, selected_vendor: str, selected_item: str, shared_tables: dict[str, pd.DataFrame]):
    vendor_options = [ALL_VENDORS]
    item_options = [ALL_ITEMS]
    preview = pd.DataFrame()
    filename = f"匯出資料_{selected_store_name}_{start}_{end}.csv"
    if export_type == "今日進貨明細":
        df = build_purchase_detail_df()
        if not df.empty:
            date_field = "delivery_date_dt" if "delivery_date_dt" in df.columns else "order_date_dt"
            df = df[df["store_id"].astype(str).str.strip() == str(selected_store_id).strip()].copy()
            df = df[(df[date_field].notna()) & (df[date_field] >= start) & (df[date_field] <= end)].copy()
        if not df.empty and "vendor_name_disp" in df.columns:
            vendor_options += clean_option_list(df["vendor_name_disp"].dropna().tolist())
        if not df.empty and "item_name_disp" in df.columns:
            item_options += clean_option_list(df["item_name_disp"].dropna().tolist())
        if not df.empty and selected_vendor != ALL_VENDORS:
            df = df[df["vendor_name_disp"].astype(str).str.strip() == selected_vendor].copy()
        if not df.empty and selected_item != ALL_ITEMS:
            df = df[df["item_name_disp"].astype(str).str.strip() == selected_item].copy()
        if not df.empty:
            preview = pd.DataFrame({"日期": pd.to_datetime(df[date_field], errors="coerce").dt.strftime("%m/%d"), "分店": selected_store_name, "廠商": df.get("vendor_name_disp", ""), "品項": df.get("item_name_disp", ""), "數量": pd.to_numeric(df.get("order_qty_num", 0), errors="coerce").fillna(0), "單位": df.get("order_unit_disp", ""), "金額": pd.to_numeric(df.get("amount_num", 0), errors="coerce").fillna(0)}).reset_index(drop=True)
        filename = f"今日進貨明細_{selected_store_name}_{start}_{end}.csv"
    elif export_type == "進銷存分析":
        df = build_analysis_with_vendor(store_id=selected_store_id, start_date=start, end_date=end, shared_tables=shared_tables)
        if not df.empty and "廠商" in df.columns:
            vendor_options += clean_option_list(df["廠商"].dropna().tolist())
        if not df.empty and "品項" in df.columns:
            item_options += clean_option_list(df["品項"].dropna().tolist())
        if not df.empty and selected_vendor != ALL_VENDORS:
            df = df[df["廠商"].astype(str).str.strip() == selected_vendor].copy()
        if not df.empty and selected_item != ALL_ITEMS:
            df = df[df["品項"].astype(str).str.strip() == selected_item].copy()
        if not df.empty:
            df = df[(df["上次庫存"] != 0) | (df["期間進貨"] != 0) | (df["期間消耗"] != 0) | (df["這次庫存"] != 0) | (df["這次叫貨"] != 0)].copy()
            preview = df[[c for c in ["日期", "廠商", "品項", "上次庫存", "期間進貨", "庫存合計", "這次庫存", "期間消耗", "這次叫貨", "日平均"] if c in df.columns]].copy().reset_index(drop=True)
            preview = format_mmdd_column(preview, "日期")
        filename = f"進銷存分析_{selected_store_name}_{start}_{end}.csv"
    else:
        df = build_history_with_vendor(store_id=selected_store_id, start_date=start, end_date=end, shared_tables=shared_tables)
        if not df.empty and "廠商" in df.columns:
            vendor_options += clean_option_list(df["廠商"].dropna().tolist())
        if not df.empty and "品項" in df.columns:
            item_options += clean_option_list(df["品項"].dropna().tolist())
        if not df.empty and selected_vendor != ALL_VENDORS:
            df = df[df["廠商"].astype(str).str.strip() == selected_vendor].copy()
        if not df.empty and selected_item != ALL_ITEMS:
            df = df[df["品項"].astype(str).str.strip() == selected_item].copy()
        if not df.empty:
            df = df[(df["上次庫存"] != 0) | (df["期間進貨"] != 0) | (df["期間消耗"] != 0) | (df["這次庫存"] != 0) | (df.get("這次叫貨", 0) != 0)].copy()
            preview = df[[c for c in ["日期顯示", "廠商", "品項", "上次庫存", "期間進貨", "庫存合計", "這次庫存", "期間消耗", "這次叫貨", "日平均"] if c in df.columns]].copy().reset_index(drop=True)
            if "日期顯示" in preview.columns:
                preview = preview.rename(columns={"日期顯示": "日期"})
            preview = format_mmdd_column(preview, "日期")
        filename = f"歷史叫貨紀錄_{selected_store_name}_{start}_{end}.csv"
    return {"vendor_options": vendor_options, "item_options": item_options, "preview": preview, "filename": filename}



def _build_base_unit_cost_lookup(items_df: pd.DataFrame, prices_df: pd.DataFrame, conversions_df: pd.DataFrame):
    if items_df.empty or prices_df.empty or "item_id" not in items_df.columns or "item_id" not in prices_df.columns:
        return {}

    items_work = items_df.copy()
    items_work["item_id"] = items_work["item_id"].astype(str).str.strip()
    if "base_unit" not in items_work.columns:
        items_work["base_unit"] = ""
    base_unit_map = dict(zip(items_work["item_id"], items_work["base_unit"].astype(str).str.strip()))

    prices_work = prices_df.copy()
    prices_work["item_id"] = prices_work["item_id"].astype(str).str.strip()
    if "price_unit" not in prices_work.columns:
        prices_work["price_unit"] = ""
    prices_work["price_unit"] = prices_work["price_unit"].astype(str).str.strip()
    if "unit_price" not in prices_work.columns:
        prices_work["unit_price"] = 0
    prices_work["unit_price"] = pd.to_numeric(prices_work["unit_price"], errors="coerce").fillna(0)
    if "effective_date" in prices_work.columns:
        prices_work["__eff"] = pd.to_datetime(prices_work["effective_date"], errors="coerce").dt.date
    else:
        prices_work["__eff"] = None
    if "end_date" in prices_work.columns:
        prices_work["__end"] = pd.to_datetime(prices_work["end_date"], errors="coerce").dt.date
    else:
        prices_work["__end"] = None
    if "is_active" in prices_work.columns:
        prices_work = prices_work[
            prices_work["is_active"].astype(str).str.strip().isin(["1", "True", "true", "YES", "yes", "是"])
        ].copy()
    if prices_work.empty:
        return {}

    conv_ratio_map = {}
    if not conversions_df.empty and {"item_id", "from_unit", "to_unit", "ratio"}.issubset(conversions_df.columns):
        conv_work = conversions_df.copy()
        conv_work["item_id"] = conv_work["item_id"].astype(str).str.strip()
        conv_work["from_unit"] = conv_work["from_unit"].astype(str).str.strip()
        conv_work["to_unit"] = conv_work["to_unit"].astype(str).str.strip()
        conv_work["ratio"] = pd.to_numeric(conv_work["ratio"], errors="coerce").fillna(0)
        conv_work = conv_work[conv_work["ratio"] != 0].copy()
        conv_ratio_map = dict(zip(zip(conv_work["item_id"], conv_work["from_unit"], conv_work["to_unit"]), conv_work["ratio"]))

    price_groups = {
        item_id: group.sort_values("__eff", ascending=True).reset_index(drop=True)
        for item_id, group in prices_work.groupby("item_id", sort=False)
    }

    lookup = {}
    for item_id, base_unit in base_unit_map.items():
        if not item_id or not base_unit:
            continue
        group = price_groups.get(item_id)
        if group is None or group.empty:
            continue
        item_lookup = {}
        for row in group.itertuples(index=False):
            unit_price = safe_float(getattr(row, "unit_price", 0), 0)
            if unit_price == 0:
                continue
            eff = getattr(row, "__eff", None)
            end = getattr(row, "__end", None)
            price_unit = str(getattr(row, "price_unit", "") or "").strip()
            if price_unit == base_unit or price_unit == "":
                base_cost = unit_price
            else:
                ratio = safe_float(conv_ratio_map.get((item_id, price_unit, base_unit), 0), 0)
                if ratio == 0:
                    continue
                base_cost = round(unit_price / ratio, 4)
            item_lookup[(eff, end)] = base_cost
        if item_lookup:
            lookup[item_id] = item_lookup
    return lookup


def _resolve_base_unit_cost(base_cost_lookup: dict, item_id: str, target_date: date | None):
    if target_date is None:
        return None
    item_lookup = base_cost_lookup.get(str(item_id).strip())
    if not item_lookup:
        return None
    matched_cost = None
    matched_eff = None
    for (eff, end), base_cost in item_lookup.items():
        if eff is not None and eff > target_date:
            continue
        if end is not None and end < target_date:
            continue
        if matched_eff is None or ((eff or date.min) >= (matched_eff or date.min)):
            matched_eff = eff
            matched_cost = base_cost
    return matched_cost


def _compute_total_stock_amount(hist_df: pd.DataFrame, shared_tables: dict[str, pd.DataFrame]):
    if hist_df.empty:
        return 0.0

    work = hist_df.copy()
    if "item_id" not in work.columns or "日期" not in work.columns:
        return 0.0
    if "這次庫存" not in work.columns:
        work["這次庫存"] = 0
    if "這次庫存_base_qty" not in work.columns:
        work["這次庫存_base_qty"] = 0

    work["item_id"] = work["item_id"].astype(str).str.strip()
    work["target_date"] = pd.to_datetime(work["日期"], errors="coerce").dt.date
    work["base_qty"] = pd.to_numeric(work["這次庫存_base_qty"], errors="coerce").fillna(0)
    fallback_qty = pd.to_numeric(work["這次庫存"], errors="coerce").fillna(0)
    work.loc[work["base_qty"] == 0, "base_qty"] = fallback_qty[work["base_qty"] == 0]
    work = work[(work["item_id"] != "") & work["target_date"].notna() & (work["base_qty"] != 0)].copy()
    if work.empty:
        return 0.0

    base_cost_lookup = _build_base_unit_cost_lookup(
        shared_tables["items"],
        shared_tables["prices"],
        get_active_df(shared_tables["unit_conversions"]),
    )
    if not base_cost_lookup:
        return 0.0

    pair_df = work[["item_id", "target_date"]].drop_duplicates().reset_index(drop=True)
    pair_df["base_unit_cost"] = [
        _resolve_base_unit_cost(base_cost_lookup, row.item_id, row.target_date)
        for row in pair_df.itertuples(index=False)
    ]
    pair_df["base_unit_cost"] = pd.to_numeric(pair_df["base_unit_cost"], errors="coerce")
    pair_df = pair_df[pair_df["base_unit_cost"].notna()].copy()
    if pair_df.empty:
        return 0.0

    work = work.merge(pair_df, on=["item_id", "target_date"], how="left")
    work = work[work["base_unit_cost"].notna()].copy()
    if work.empty:
        return 0.0
    return float((work["base_qty"] * work["base_unit_cost"]).sum())


def _get_analysis_page_cache(signature, upstream: dict, shared_tables: dict[str, pd.DataFrame]):
    cache_root = st.session_state.setdefault("_analysis_page_vm_cache", {})
    cache = cache_root.get(signature)
    if isinstance(cache, dict):
        return cache

    purchase_filt = upstream["purchase_filt"]
    base_detail_df = upstream["base_detail_df"]
    vendor_summary = upstream["vendor_summary"]

    cache = {
        "total_purchase_amount_all": float(purchase_filt["進貨金額"].sum()) if (not purchase_filt.empty and "進貨金額" in purchase_filt.columns) else 0.0,
        "total_purchase_amount_map": None,
        "total_stock_amount_all": _compute_total_stock_amount(base_detail_df, shared_tables),
        "total_stock_amount_map": {},
        "vendor_summary_map": None,
        "purchase_filt_map": {},
        "detail_df_map": {},
        "detail_display_map": {},
    }
    cache_root[signature] = cache
    return cache


def _get_analysis_vendor_purchase_df(cache: dict, purchase_filt: pd.DataFrame, selected_vendor: str):
    if selected_vendor == ALL_VENDORS:
        return purchase_filt
    purchase_map = cache["purchase_filt_map"]
    if selected_vendor not in purchase_map:
        if purchase_filt.empty or "廠商" not in purchase_filt.columns:
            purchase_map[selected_vendor] = pd.DataFrame()
        else:
            purchase_map[selected_vendor] = purchase_filt.loc[purchase_filt["廠商"].eq(selected_vendor)].copy()
    return purchase_map[selected_vendor]


def _get_analysis_vendor_detail_df(cache: dict, base_detail_df: pd.DataFrame, selected_vendor: str):
    if selected_vendor == ALL_VENDORS:
        return base_detail_df
    detail_map = cache["detail_df_map"]
    if selected_vendor not in detail_map:
        if base_detail_df.empty or "廠商" not in base_detail_df.columns:
            detail_map[selected_vendor] = pd.DataFrame()
        else:
            detail_map[selected_vendor] = base_detail_df.loc[base_detail_df["廠商"].eq(selected_vendor)].copy()
    return detail_map[selected_vendor]




def _get_analysis_vendor_purchase_total(cache: dict, purchase_filt: pd.DataFrame, selected_vendor: str):
    if selected_vendor == ALL_VENDORS:
        return cache["total_purchase_amount_all"]
    total_purchase_amount_map = cache.get("total_purchase_amount_map")
    if total_purchase_amount_map is None:
        total_purchase_amount_map = {}
        if not purchase_filt.empty and {"廠商", "進貨金額"}.issubset(purchase_filt.columns):
            vendor_purchase_totals = (
                purchase_filt.groupby("廠商", sort=False)["進貨金額"]
                .sum()
                .reset_index()
            )
            total_purchase_amount_map = dict(zip(vendor_purchase_totals["廠商"], vendor_purchase_totals["進貨金額"]))
        cache["total_purchase_amount_map"] = total_purchase_amount_map
    return float(total_purchase_amount_map.get(selected_vendor, 0.0))


def _get_analysis_vendor_summary(cache: dict, vendor_summary: pd.DataFrame, selected_vendor: str):
    if selected_vendor == ALL_VENDORS:
        return vendor_summary
    vendor_summary_map = cache.get("vendor_summary_map")
    if vendor_summary_map is None:
        vendor_summary_map = {}
        if not vendor_summary.empty and "廠商" in vendor_summary.columns:
            vendor_summary_map = {
                str(vendor): group.reset_index(drop=True).copy()
                for vendor, group in vendor_summary.groupby("廠商", sort=False)
            }
        cache["vendor_summary_map"] = vendor_summary_map
    return vendor_summary_map.get(selected_vendor, pd.DataFrame())

def _get_analysis_vendor_total_stock_amount(cache: dict, detail_df: pd.DataFrame, selected_vendor: str, shared_tables: dict[str, pd.DataFrame]):
    if selected_vendor == ALL_VENDORS:
        return cache["total_stock_amount_all"]
    total_map = cache["total_stock_amount_map"]
    if selected_vendor not in total_map:
        total_map[selected_vendor] = _compute_total_stock_amount(detail_df, shared_tables)
    return total_map[selected_vendor]


def _get_analysis_detail_frames(cache: dict, detail_df: pd.DataFrame, selected_vendor: str, display_mode: str):
    cache_key = (selected_vendor, display_mode)
    display_map = cache["detail_display_map"]
    if cache_key not in display_map:
        display_map[cache_key] = _build_report_detail_frames(
            detail_df=detail_df,
            selected_vendor=selected_vendor,
            display_mode=display_mode,
            date_col="日期",
            full_cols=["日期", "品項", "上次庫存", "期間進貨", "庫存合計", "這次庫存", "期間消耗", "這次叫貨", "日平均"],
        )
    export_df, show_df = display_map[cache_key]
    return export_df, show_df


def build_analysis_page_view_model(store_id: str, start: date, end: date, selected_vendor: str, display_mode: str, shared_tables: dict[str, pd.DataFrame]):
    upstream = _build_history_analysis_shared_upstream(store_id=store_id, start_date=start, end_date=end, shared_tables=shared_tables)
    hist_df = upstream["hist_df"]
    purchase_filt = upstream["purchase_filt"]
    vendor_options = upstream["vendor_options"]
    base_detail_df = upstream["base_detail_df"]
    vendor_summary = upstream["vendor_summary"]

    upstream_cache = st.session_state.get("_history_analysis_upstream_cache", {})
    upstream_signature = upstream_cache.get("signature")
    cache = _get_analysis_page_cache(upstream_signature, upstream, shared_tables)

    if selected_vendor == ALL_VENDORS:
        detail_df = base_detail_df
        total_purchase_amount = cache["total_purchase_amount_all"]
        total_stock_amount = cache["total_stock_amount_all"]
        export_df, show_df = _get_analysis_detail_frames(cache, detail_df, selected_vendor, display_mode)
    else:
        purchase_filt = _get_analysis_vendor_purchase_df(cache, purchase_filt, selected_vendor)
        detail_df = _get_analysis_vendor_detail_df(cache, base_detail_df, selected_vendor)
        total_purchase_amount = _get_analysis_vendor_purchase_total(cache, purchase_filt, selected_vendor)
        total_stock_amount = _get_analysis_vendor_total_stock_amount(cache, detail_df, selected_vendor, shared_tables)
        vendor_summary = _get_analysis_vendor_summary(cache, vendor_summary, selected_vendor)
        export_df, show_df = _get_analysis_detail_frames(cache, detail_df, selected_vendor, display_mode)

    return {"hist_df": hist_df, "purchase_filt": purchase_filt, "vendor_options": vendor_options, "total_purchase_amount": total_purchase_amount, "total_stock_amount": total_stock_amount, "vendor_summary": vendor_summary, "detail_df": detail_df, "export_df": export_df, "show_df": show_df}




def build_analysis_vendor_summary_display_model(vendor_summary: pd.DataFrame, display_mode: str):
    if vendor_summary is None or vendor_summary.empty:
        return {"show_df": pd.DataFrame(), "csv_payload": b""}
    show_df = format_mmdd_column(vendor_summary.copy(), "日期")
    if display_mode == DISPLAY_MODE_MOBILE and "廠商" in show_df.columns:
        show_df["廠商"] = show_df["廠商"].apply(lambda x: short_item_name(x, 10))
    return {"show_df": show_df, "csv_payload": build_csv_download_payload(vendor_summary)}


def build_analysis_detail_download_payload(export_df: pd.DataFrame) -> bytes:
    return build_csv_download_payload(export_df)


def build_history_download_payload(export_df: pd.DataFrame) -> bytes:
    return build_csv_download_payload(export_df)


def build_analysis_vendor_summary_section(model: dict, display_mode: str):
    vendor_summary = model.get("vendor_summary", pd.DataFrame())
    if vendor_summary is None or vendor_summary.empty:
        return {"has_data": False, "show_df": pd.DataFrame(), "csv_payload": b""}
    vendor_summary_model = build_analysis_vendor_summary_display_model(vendor_summary, display_mode)
    return {
        "has_data": not vendor_summary_model["show_df"].empty,
        "show_df": vendor_summary_model["show_df"],
        "csv_payload": vendor_summary_model["csv_payload"],
    }


def build_analysis_detail_section(model: dict):
    export_df = model.get("export_df", pd.DataFrame())
    show_df = model.get("show_df", pd.DataFrame())
    return {
        "has_data": show_df is not None and not show_df.empty,
        "show_df": show_df,
        "csv_payload": build_analysis_detail_download_payload(export_df),
    }


def resolve_history_filter_state(*, selected_vendor: str, previous_vendor: str, current_item_filter: str, item_options: list[str], default_item: str):
    resolved_item_filter = current_item_filter
    resolved_previous_vendor = selected_vendor
    if previous_vendor != selected_vendor:
        resolved_item_filter = default_item
    if resolved_item_filter not in item_options:
        resolved_item_filter = default_item
    return {
        "item_filter": resolved_item_filter,
        "previous_vendor": resolved_previous_vendor,
    }


def build_history_detail_section(model: dict):
    export_df = model.get("export_df", pd.DataFrame())
    show_df = model.get("show_df", pd.DataFrame())
    detail_df = model.get("detail_df", pd.DataFrame())
    return {
        "detail_df": detail_df,
        "has_data": detail_df is not None and not detail_df.empty,
        "show_df": show_df,
        "csv_payload": build_history_download_payload(export_df),
    }

def build_cost_debug_selector_data(shared_tables: dict[str, pd.DataFrame]):
    items_df = get_active_df(shared_tables["items"])
    if items_df.empty:
        return {"items_df": items_df, "work": pd.DataFrame(), "item_options": []}
    work = items_df.copy()
    work["item_label"] = work.apply(lambda r: f"{item_display_name(r)} ({norm(r.get('item_id', ''))})", axis=1)
    work = work.sort_values("item_label")
    return {"items_df": items_df, "work": work, "item_options": work["item_id"].astype(str).tolist()}


def build_cost_debug_view_model(shared_tables: dict[str, pd.DataFrame], selected_item_id: str, target_date: date):
    def _safe_to_date(x):
        dt = pd.to_datetime(x, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.date()

    items_df = get_active_df(shared_tables["items"])
    prices_df = shared_tables["prices"]
    conversions_df = get_active_df(shared_tables["unit_conversions"])
    units_df = shared_tables.get("units", pd.DataFrame())
    work = build_cost_debug_selector_data(shared_tables)["work"]
    selected = str(selected_item_id).strip()

    if work.empty:
        item_row = pd.Series(dtype=object)
        selected = ""
    else:
        mask = work["item_id"].astype(str).str.strip() == selected
        if not selected or not mask.any():
            item_row = work.iloc[0]
            selected = str(item_row.get("item_id", "")).strip()
        else:
            item_row = work.loc[mask].iloc[0]

    unit_map = {}
    if not units_df.empty and "unit_id" in units_df.columns:
        units_work = units_df.copy()
        units_work["unit_id"] = units_work["unit_id"].astype(str).str.strip()

        units_work["unit_name_disp"] = units_work.get("unit_name_zh", "").astype(str).str.strip()
        if "unit_name" in units_work.columns:
            units_work.loc[units_work["unit_name_disp"] == "", "unit_name_disp"] = (
                units_work["unit_name"].astype(str).str.strip()
            )

        units_work.loc[units_work["unit_name_disp"] == "", "unit_name_disp"] = units_work["unit_id"]
        unit_map = dict(zip(units_work["unit_id"], units_work["unit_name_disp"]))

    base_unit_id = norm(item_row.get("base_unit", ""))
    base_unit = unit_map.get(base_unit_id, base_unit_id)

    default_stock_unit_id = norm(item_row.get("default_stock_unit", ""))
    default_stock_unit = unit_map.get(default_stock_unit_id, default_stock_unit_id)

    default_order_unit_id = norm(item_row.get("default_order_unit", ""))
    default_order_unit = unit_map.get(default_order_unit_id, default_order_unit_id)

    price_rows = prices_df.copy()
    if not price_rows.empty and "item_id" in price_rows.columns:
        price_rows = price_rows[
            price_rows["item_id"].astype(str).str.strip() == selected
        ].copy()

        if "is_active" in price_rows.columns:
            price_rows = price_rows[
                price_rows["is_active"].apply(
                    lambda x: str(x).strip() in ["1", "True", "true", "YES", "yes", "是"]
                )
            ].copy()

        if "effective_date" in price_rows.columns:
            price_rows["__eff"] = price_rows["effective_date"].apply(_safe_to_date)
        else:
            price_rows["__eff"] = None

        if "end_date" in price_rows.columns:
            price_rows["__end"] = price_rows["end_date"].apply(_safe_to_date)
        else:
            price_rows["__end"] = None

        price_rows = price_rows[
            (price_rows["__eff"].isna() | (price_rows["__eff"] <= target_date))
            & (price_rows["__end"].isna() | (price_rows["__end"] >= target_date))
        ].copy()

        if not price_rows.empty:
            latest_price = price_rows.sort_values("__eff", ascending=True).iloc[-1]
            unit_price = float(latest_price.get("unit_price", 0) or 0)
            price_unit_id = norm(latest_price.get("price_unit", ""))
            price_unit = unit_map.get(price_unit_id, price_unit_id)
            effective_date = latest_price.get("effective_date", "")
        else:
            unit_price = 0.0
            price_unit = ""
            effective_date = ""
    else:
        unit_price = 0.0
        price_unit = ""
        effective_date = ""

    base_unit_cost = get_base_unit_cost(
        item_id=selected,
        target_date=target_date,
        items_df=items_df,
        prices_df=prices_df,
        conversions_df=conversions_df,
    )

    conv_show = conversions_df.copy()
    if not conv_show.empty and "item_id" in conv_show.columns:
        conv_show = conv_show[conv_show["item_id"].astype(str).str.strip() == selected].copy()

    return {
        "item_row": item_row,
        "base_unit": base_unit,
        "default_stock_unit": default_stock_unit,
        "default_order_unit": default_order_unit,
        "unit_price": unit_price,
        "price_unit": price_unit,
        "effective_date": effective_date,
        "base_unit_cost": base_unit_cost,
        "conv_show": conv_show,
    }

def build_csv_download_payload(preview: pd.DataFrame) -> bytes:
    if preview is None or preview.empty:
        return b""
    return preview.to_csv(index=False).encode("utf-8-sig")


def get_selected_item_label(work: pd.DataFrame, selected_item_id) -> str:
    if work is None or work.empty or "item_id" not in work.columns or "item_label" not in work.columns:
        return ""
    selected = str(selected_item_id).strip()
    mask = work["item_id"].astype(str).str.strip() == selected
    if not mask.any():
        return ""
    return str(work.loc[mask, "item_label"].iloc[0])


def build_cost_debug_display_model(shared_tables: dict[str, pd.DataFrame], selected_item_id, target_date):
    selector = build_cost_debug_selector_data(shared_tables)
    work = selector["work"]
    selector["item_label_map"] = dict(zip(work["item_id"].astype(str).str.strip(), work["item_label"].astype(str))) if not work.empty and {"item_id", "item_label"}.issubset(work.columns) else {}
    item_label = get_selected_item_label(work, selected_item_id)
    model = build_cost_debug_view_model(shared_tables, selected_item_id, target_date)
    conv_show = model["conv_show"]
    conv_columns = [c for c in ["conversion_id", "from_unit", "to_unit", "ratio", "is_active"] if c in conv_show.columns]
    return {
        "selector": selector,
        "item_label": item_label,
        "item_name": item_label.rsplit(" (", 1)[0] if item_label else "",
        "model": model,
        "conv_display": conv_show[conv_columns].copy() if conv_columns else pd.DataFrame(),
    }
