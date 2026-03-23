from __future__ import annotations

from datetime import date

import pandas as pd

from oms_core import (
    _build_inventory_history_summary_df,
    _build_latest_item_metrics_df,
    _build_purchase_detail_df,
    _clean_option_list,
    _get_active_df,
    _item_display_name,
    _norm,
    _parse_date,
    _safe_float,
    get_base_unit_cost,
)
from utils.utils_units import convert_unit, get_base_unit


ALL_VENDORS = "全部廠商"
ALL_ITEMS = "全部品項"
DISPLAY_MODE_MOBILE = "手機精簡"
DISPLAY_MODE_FULL = "完整報表"


def build_history_with_vendor(store_id: str, start_date: date, end_date: date, shared_tables: dict[str, pd.DataFrame]):
    hist_df = _build_inventory_history_summary_df(store_id=store_id, start_date=start_date, end_date=end_date)
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
    if "item_id" not in items_map.columns or "default_vendor_id" not in items_map.columns:
        hist_df["廠商"] = "-"
        return hist_df
    items_map["item_id"] = items_map["item_id"].astype(str).str.strip()
    items_map["default_vendor_id"] = items_map["default_vendor_id"].astype(str).str.strip()
    items_map = items_map[["item_id", "default_vendor_id"]].drop_duplicates()
    vendors_map = vendors_df.copy()
    if "vendor_id" not in vendors_map.columns:
        hist_df["廠商"] = "-"
        return hist_df
    vendors_map["vendor_id"] = vendors_map["vendor_id"].astype(str).str.strip()
    vendors_map["廠商"] = vendors_map.apply(lambda r: _norm(r.get("vendor_name", "")) or _norm(r.get("vendor_id", "")) or "-", axis=1)
    vendors_map = vendors_map[["vendor_id", "廠商"]].drop_duplicates()
    merged = hist_df.merge(items_map, on="item_id", how="left")
    merged = merged.merge(vendors_map, left_on="default_vendor_id", right_on="vendor_id", how="left")
    merged["廠商"] = merged["廠商"].fillna("-")
    for col in ["default_vendor_id", "vendor_id"]:
        if col in merged.columns:
            merged = merged.drop(columns=[col])
    return merged


def build_analysis_with_vendor(store_id: str, start_date: date, end_date: date, shared_tables: dict[str, pd.DataFrame]):
    hist_df = _build_inventory_history_summary_df(store_id=store_id, start_date=start_date, end_date=end_date)
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
    vendors_map["廠商"] = vendors_map.apply(lambda r: _norm(r.get("vendor_name", "")) or _norm(r.get("vendor_id", "")) or "-", axis=1)
    vendors_map = vendors_map[["vendor_id", "廠商"]].drop_duplicates()
    merged = hist_df.merge(items_map, on="item_id", how="left")
    merged = merged.merge(vendors_map, left_on="default_vendor_id", right_on="vendor_id", how="left")
    merged["廠商"] = merged["廠商"].fillna("-")
    for col in ["default_vendor_id", "vendor_id"]:
        if col in merged.columns:
            merged = merged.drop(columns=[col])
    return merged


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
    qty = _safe_float(qty, 0)
    item_id = _norm(item_id)
    target_unit = _norm(target_unit)
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
    latest_df = _build_latest_item_metrics_df(store_id=store_id, as_of_date=selected_date)
    if latest_df.empty:
        return {"preview": pd.DataFrame(), "vendor_options": [ALL_VENDORS], "has_source": False}
    work = latest_df.copy()
    if "日期_dt" in work.columns:
        work = work[pd.to_datetime(work["日期_dt"], errors="coerce").dt.date == selected_date].copy()
    elif "日期" in work.columns:
        work = work[pd.to_datetime(work["日期"], errors="coerce").dt.date == selected_date].copy()
    if work.empty:
        return {"preview": pd.DataFrame(), "vendor_options": [ALL_VENDORS], "has_source": True}
    if "這次庫存" not in work.columns:
        work["這次庫存"] = 0
    if "這次叫貨" not in work.columns:
        work["這次叫貨"] = 0
    work["這次庫存"] = pd.to_numeric(work["這次庫存"], errors="coerce").fillna(0)
    work["這次叫貨"] = pd.to_numeric(work["這次叫貨"], errors="coerce").fillna(0)
    work = work[(work["這次庫存"] != 0) | (work["這次叫貨"] != 0)].copy()
    if work.empty:
        return {"preview": pd.DataFrame(), "vendor_options": [ALL_VENDORS], "has_source": True}
    items_df = shared_tables["items"]
    vendors_df = shared_tables["vendors"]
    conversions_df = _get_active_df(shared_tables["unit_conversions"])
    stock_unit_map = {}
    order_unit_map = {}
    if not items_df.empty and "item_id" in items_df.columns:
        items_df = items_df.copy()
        items_df["item_id"] = items_df["item_id"].astype(str).str.strip()
        if "default_stock_unit" in items_df.columns:
            stock_unit_map = dict(zip(items_df["item_id"], items_df["default_stock_unit"].astype(str).str.strip()))
        if "default_order_unit" in items_df.columns:
            order_unit_map = dict(zip(items_df["item_id"], items_df["default_order_unit"].astype(str).str.strip()))
    if not vendors_df.empty and "vendor_id" in vendors_df.columns:
        vendors_df = vendors_df.copy()
        vendors_df["vendor_id"] = vendors_df["vendor_id"].astype(str).str.strip()
        vendors_df["vendor_name_disp"] = vendors_df.apply(lambda r: _norm(r.get("vendor_name_zh", "")) or _norm(r.get("vendor_name", "")) or _norm(r.get("vendor_id", "")) or "-", axis=1)
        vendor_map = dict(zip(vendors_df["vendor_id"], vendors_df["vendor_name_disp"]))
        if "vendor_id" in work.columns:
            work["廠商"] = work["vendor_id"].astype(str).str.strip().map(vendor_map).fillna("-")
        elif not items_df.empty and {"item_id", "default_vendor_id"}.issubset(items_df.columns):
            item_vendor = items_df[["item_id", "default_vendor_id"]].copy()
            item_vendor["item_id"] = item_vendor["item_id"].astype(str).str.strip()
            item_vendor["default_vendor_id"] = item_vendor["default_vendor_id"].astype(str).str.strip()
            work = work.merge(item_vendor, on="item_id", how="left")
            work["廠商"] = work["default_vendor_id"].astype(str).str.strip().map(vendor_map).fillna("-")
        else:
            work["廠商"] = "-"
    else:
        work["廠商"] = "-"
    vendor_options = [ALL_VENDORS] + _clean_option_list(work["廠商"].dropna().tolist())
    if selected_vendor != ALL_VENDORS:
        work = work[work["廠商"].astype(str).str.strip() == selected_vendor].copy()
    work["庫存顯示單位"] = work["item_id"].astype(str).str.strip().map(stock_unit_map).fillna("")
    work["叫貨顯示單位"] = work["item_id"].astype(str).str.strip().map(order_unit_map).fillna("")
    work["這次庫存_顯示值"] = work.apply(lambda r: convert_compare_qty_to_display_unit(qty=r.get("這次庫存", 0), item_id=r.get("item_id", ""), target_unit=r.get("庫存顯示單位", ""), items_df=items_df, conversions_df=conversions_df, as_of_date=selected_date), axis=1)
    work["這次叫貨_顯示值"] = work.apply(lambda r: convert_compare_qty_to_display_unit(qty=r.get("這次叫貨", 0), item_id=r.get("item_id", ""), target_unit=r.get("叫貨顯示單位", ""), items_df=items_df, conversions_df=conversions_df, as_of_date=selected_date), axis=1)
    item_col = "品項" if "品項" in work.columns else "item_id"
    preview = work[["廠商", item_col, "這次庫存_顯示值", "庫存顯示單位", "這次叫貨_顯示值", "叫貨顯示單位"]].copy()
    preview = preview.rename(columns={item_col: "品項", "這次庫存_顯示值": "這次庫存", "這次叫貨_顯示值": "這次叫貨"})
    preview["這次庫存"] = preview.apply(lambda r: f"{_safe_float(r['這次庫存']):g} {str(r['庫存顯示單位']).strip()}".strip(), axis=1)
    preview["這次叫貨"] = preview.apply(lambda r: f"{_safe_float(r['這次叫貨']):g} {str(r['叫貨顯示單位']).strip()}".strip(), axis=1)
    preview = preview.drop(columns=["庫存顯示單位", "叫貨顯示單位"]).sort_values(["廠商", "品項"], ascending=[True, True]).reset_index(drop=True)
    return {"preview": preview, "vendor_options": vendor_options, "has_source": True}

def build_history_page_view_model(store_id: str, start_date: date, end_date: date, selected_vendor: str, selected_item: str, display_mode: str, shared_tables: dict[str, pd.DataFrame]):
    hist_df = build_history_with_vendor(store_id=store_id, start_date=start_date, end_date=end_date, shared_tables=shared_tables)
    if hist_df.empty:
        return {"hist_df": hist_df, "vendor_options": [ALL_VENDORS], "item_options": [ALL_ITEMS], "detail_df": pd.DataFrame(), "export_df": pd.DataFrame(), "show_df": pd.DataFrame()}
    vendor_values = _clean_option_list(hist_df["廠商"].dropna().tolist()) if "廠商" in hist_df.columns else []
    vendor_options = [ALL_VENDORS] + vendor_values
    items_df = shared_tables["items"].copy()
    vendors_df = shared_tables["vendors"].copy()
    item_values = []
    if not items_df.empty:
        items_df.columns = [str(c).strip() for c in items_df.columns]
        items_df["item_id"] = items_df.get("item_id", "").astype(str).str.strip()
        items_df["default_vendor_id"] = items_df.get("default_vendor_id", "").astype(str).str.strip()
        items_df["品項顯示"] = items_df.apply(lambda r: _norm(r.get("item_name_zh", "")) or _norm(r.get("item_name", "")) or _norm(r.get("item_id", "")), axis=1)
        if "is_active" in items_df.columns:
            items_df = items_df[items_df["is_active"].astype(str).str.strip().isin(["1", "True", "true", "YES", "yes", "是"])].copy()
        if selected_vendor != ALL_VENDORS and not vendors_df.empty:
            vendors_df.columns = [str(c).strip() for c in vendors_df.columns]
            vendors_df["vendor_id"] = vendors_df.get("vendor_id", "").astype(str).str.strip()
            vendors_df["vendor_name_norm"] = vendors_df.apply(lambda r: _norm(r.get("vendor_name", "")) or _norm(r.get("vendor_id", "")), axis=1)
            target_vendor = vendors_df[vendors_df["vendor_name_norm"].astype(str).str.strip() == str(selected_vendor).strip()].copy()
            if not target_vendor.empty:
                target_vendor_id = str(target_vendor.iloc[0]["vendor_id"]).strip()
                items_df = items_df[items_df["default_vendor_id"].astype(str).str.strip() == target_vendor_id].copy()
            else:
                items_df = items_df.iloc[0:0].copy()
        item_values = _clean_option_list(items_df["品項顯示"].dropna().tolist())
    item_options = [ALL_ITEMS] + item_values
    filt_df = hist_df.copy()
    if selected_vendor != ALL_VENDORS:
        filt_df = filt_df[filt_df["廠商"] == selected_vendor].copy()
    if selected_item != ALL_ITEMS:
        filt_df = filt_df[filt_df["品項"].astype(str).str.strip() == str(selected_item).strip()].copy()
    detail_df = filt_df.copy()
    detail_df = detail_df[(detail_df["上次庫存"] != 0) | (detail_df["期間進貨"] != 0) | (detail_df["期間消耗"] != 0) | (detail_df["這次庫存"] != 0) | (detail_df.get("這次叫貨", 0) != 0)].copy()
    export_df = pd.DataFrame()
    show_df = pd.DataFrame()
    if not detail_df.empty and selected_vendor != ALL_VENDORS:
        full_cols = ["日期顯示", "品項", "上次庫存", "期間進貨", "庫存合計", "這次庫存", "期間消耗", "這次叫貨", "日平均"]
        export_df = detail_df[full_cols].copy().reset_index(drop=True)
        export_df = format_mmdd_column(export_df, "日期顯示")
        if display_mode == DISPLAY_MODE_MOBILE:
            show_df = export_df[["日期顯示", "品項", "這次庫存", "這次叫貨", "日平均"]].copy()
            show_df["品項"] = show_df["品項"].apply(short_item_name)
        else:
            show_df = export_df.copy()
    return {"hist_df": hist_df, "vendor_options": vendor_options, "item_options": item_options, "detail_df": detail_df, "export_df": export_df, "show_df": show_df}


def build_export_view_model(export_type: str, selected_store_id: str, selected_store_name: str, start: date, end: date, selected_vendor: str, selected_item: str, shared_tables: dict[str, pd.DataFrame]):
    vendor_options = [ALL_VENDORS]
    item_options = [ALL_ITEMS]
    preview = pd.DataFrame()
    filename = f"匯出資料_{selected_store_name}_{start}_{end}.csv"
    if export_type == "今日進貨明細":
        df = _build_purchase_detail_df()
        if not df.empty:
            date_field = "delivery_date_dt" if "delivery_date_dt" in df.columns else "order_date_dt"
            df = df[df["store_id"].astype(str).str.strip() == str(selected_store_id).strip()].copy()
            df = df[(df[date_field].notna()) & (df[date_field] >= start) & (df[date_field] <= end)].copy()
        if not df.empty and "vendor_name_disp" in df.columns:
            vendor_options += _clean_option_list(df["vendor_name_disp"].dropna().tolist())
        if not df.empty and "item_name_disp" in df.columns:
            item_options += _clean_option_list(df["item_name_disp"].dropna().tolist())
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
            vendor_options += _clean_option_list(df["廠商"].dropna().tolist())
        if not df.empty and "品項" in df.columns:
            item_options += _clean_option_list(df["品項"].dropna().tolist())
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
            vendor_options += _clean_option_list(df["廠商"].dropna().tolist())
        if not df.empty and "品項" in df.columns:
            item_options += _clean_option_list(df["品項"].dropna().tolist())
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

def build_analysis_page_view_model(store_id: str, start: date, end: date, selected_vendor: str, display_mode: str, shared_tables: dict[str, pd.DataFrame]):
    hist_df = build_analysis_with_vendor(store_id=store_id, start_date=start, end_date=end, shared_tables=shared_tables)
    po_detail_df = _build_purchase_detail_df()
    purchase_filt = pd.DataFrame()
    if not po_detail_df.empty:
        date_field = "delivery_date_dt" if "delivery_date_dt" in po_detail_df.columns else "order_date_dt"
        purchase_filt = po_detail_df[(po_detail_df["store_id"].astype(str).str.strip() == str(store_id).strip()) & (po_detail_df[date_field].notna()) & (po_detail_df[date_field] >= start) & (po_detail_df[date_field] <= end)].copy()
        purchase_filt["日期"] = pd.to_datetime(purchase_filt[date_field], errors="coerce").dt.strftime("%m/%d")
        purchase_filt["廠商"] = purchase_filt["vendor_name_disp"].apply(lambda x: _norm(x) or "-")
        purchase_filt["進貨金額"] = pd.to_numeric(purchase_filt["amount_num"], errors="coerce").fillna(0)
    hist_filt = hist_df.copy()
    if not hist_filt.empty and "廠商" in hist_filt.columns:
        vendor_values = _clean_option_list(hist_filt["廠商"].dropna().tolist())
    elif not purchase_filt.empty and "廠商" in purchase_filt.columns:
        vendor_values = _clean_option_list(purchase_filt["廠商"].dropna().tolist())
    else:
        vendor_values = []
    vendor_options = [ALL_VENDORS] + vendor_values
    if selected_vendor != ALL_VENDORS:
        if not hist_filt.empty and "廠商" in hist_filt.columns:
            hist_filt = hist_filt[hist_filt["廠商"] == selected_vendor].copy()
        if not purchase_filt.empty and "廠商" in purchase_filt.columns:
            purchase_filt = purchase_filt[purchase_filt["廠商"] == selected_vendor].copy()
    total_purchase_amount = float(pd.to_numeric(purchase_filt["進貨金額"], errors="coerce").fillna(0).sum()) if (not purchase_filt.empty and "進貨金額" in purchase_filt.columns) else 0.0
    total_stock_amount = 0.0
    if not hist_filt.empty:
        work_stock = hist_filt.copy()
        if "這次庫存" not in work_stock.columns:
            work_stock["這次庫存"] = 0
        if "這次庫存_base_qty" not in work_stock.columns:
            work_stock["這次庫存_base_qty"] = 0
        items_df = shared_tables["items"]
        prices_df = shared_tables["prices"]
        conversions_df = _get_active_df(shared_tables["unit_conversions"])
        work_stock["這次庫存"] = pd.to_numeric(work_stock["這次庫存"], errors="coerce").fillna(0)
        work_stock["這次庫存_base_qty"] = pd.to_numeric(work_stock["這次庫存_base_qty"], errors="coerce").fillna(0)
        def _calc_stock_amount(row):
            item_id = _norm(row.get("item_id", ""))
            base_qty = _safe_float(row.get("這次庫存_base_qty", 0))
            row_date = row.get("日期")
            if not item_id:
                return 0.0
            target_date = _parse_date(row_date)
            if target_date is None:
                return 0.0
            if base_qty == 0:
                qty = _safe_float(row.get("這次庫存", 0))
                if qty == 0:
                    return 0.0
                base_qty = qty
            base_unit_cost = get_base_unit_cost(item_id=item_id, target_date=target_date, items_df=items_df, prices_df=prices_df, conversions_df=conversions_df)
            return 0.0 if base_unit_cost is None else round(base_qty * float(base_unit_cost), 2)
        work_stock["庫存總額"] = work_stock.apply(_calc_stock_amount, axis=1)
        total_stock_amount = float(pd.to_numeric(work_stock["庫存總額"], errors="coerce").fillna(0).sum())
    vendor_summary = purchase_filt.groupby(["日期", "廠商"], as_index=False)["進貨金額"].sum().sort_values(["日期", "廠商"], ascending=[False, True]).reset_index(drop=True) if not purchase_filt.empty else pd.DataFrame()
    detail_df = hist_filt.copy()
    if not detail_df.empty and "日期" in detail_df.columns:
        if pd.api.types.is_numeric_dtype(detail_df["日期"]):
            detail_df["日期"] = pd.to_datetime(detail_df["日期"], unit="s", errors="coerce").dt.strftime("%m/%d")
        else:
            detail_df["日期"] = pd.to_datetime(detail_df["日期"], errors="coerce").dt.strftime("%m/%d")
        detail_df = detail_df[(detail_df["上次庫存"] != 0) | (detail_df["期間進貨"] != 0) | (detail_df["期間消耗"] != 0) | (detail_df["這次庫存"] != 0) | (detail_df["這次叫貨"] != 0)].copy()
    export_df = pd.DataFrame()
    show_df = pd.DataFrame()
    if not detail_df.empty and selected_vendor != ALL_VENDORS:
        show_cols = ["日期", "品項", "上次庫存", "期間進貨", "庫存合計", "這次庫存", "期間消耗", "這次叫貨", "日平均"]
        export_df = detail_df[show_cols].copy().reset_index(drop=True)
        export_df = format_mmdd_column(export_df, "日期")
        if display_mode == DISPLAY_MODE_MOBILE:
            show_df = export_df[["日期", "品項", "這次庫存", "這次叫貨", "日平均"]].copy()
            show_df["品項"] = show_df["品項"].apply(short_item_name)
        else:
            show_df = export_df.copy()
    return {"hist_df": hist_df, "purchase_filt": purchase_filt, "vendor_options": vendor_options, "total_purchase_amount": total_purchase_amount, "total_stock_amount": total_stock_amount, "vendor_summary": vendor_summary, "detail_df": detail_df, "export_df": export_df, "show_df": show_df}


def build_cost_debug_selector_data(shared_tables: dict[str, pd.DataFrame]):
    items_df = _get_active_df(shared_tables["items"])
    if items_df.empty:
        return {"items_df": items_df, "work": pd.DataFrame(), "item_options": []}
    work = items_df.copy()
    work["item_label"] = work.apply(lambda r: f"{_item_display_name(r)} ({_norm(r.get('item_id', ''))})", axis=1)
    work = work.sort_values("item_label")
    return {"items_df": items_df, "work": work, "item_options": work["item_id"].astype(str).tolist()}


def build_cost_debug_view_model(shared_tables: dict[str, pd.DataFrame], selected_item_id: str, target_date: date):
    items_df = _get_active_df(shared_tables["items"])
    prices_df = shared_tables["prices"]
    conversions_df = _get_active_df(shared_tables["unit_conversions"])
    work = build_cost_debug_selector_data(shared_tables)["work"]
    item_row = work[work["item_id"].astype(str).str.strip() == str(selected_item_id).strip()].iloc[0]
    base_unit = _norm(item_row.get("base_unit", ""))
    default_stock_unit = _norm(item_row.get("default_stock_unit", ""))
    default_order_unit = _norm(item_row.get("default_order_unit", ""))
    price_rows = prices_df.copy()
    if not price_rows.empty and "item_id" in price_rows.columns:
        price_rows = price_rows[price_rows["item_id"].astype(str).str.strip() == str(selected_item_id).strip()].copy()
        if "is_active" in price_rows.columns:
            price_rows = price_rows[price_rows["is_active"].apply(lambda x: str(x).strip() in ["1", "True", "true", "YES", "yes", "是"])].copy()
        if "effective_date" in price_rows.columns:
            price_rows["__eff"] = price_rows["effective_date"].apply(lambda x: None if str(x).strip() == "" else pd.to_datetime(x).date())
        else:
            price_rows["__eff"] = None
        if "end_date" in price_rows.columns:
            price_rows["__end"] = price_rows["end_date"].apply(lambda x: None if str(x).strip() == "" else pd.to_datetime(x).date())
        else:
            price_rows["__end"] = None
        price_rows = price_rows[(price_rows["__eff"].isna() | (price_rows["__eff"] <= target_date)) & (price_rows["__end"].isna() | (price_rows["__end"] >= target_date))].copy()
        if not price_rows.empty:
            latest_price = price_rows.sort_values("__eff", ascending=True).iloc[-1]
            unit_price = float(latest_price.get("unit_price", 0) or 0)
            price_unit = _norm(latest_price.get("price_unit", ""))
            effective_date = latest_price.get("effective_date", "")
        else:
            unit_price = 0.0
            price_unit = ""
            effective_date = ""
    else:
        unit_price = 0.0
        price_unit = ""
        effective_date = ""
    base_unit_cost = get_base_unit_cost(item_id=selected_item_id, target_date=target_date, items_df=items_df, prices_df=prices_df, conversions_df=conversions_df)
    conv_show = conversions_df.copy()
    if not conv_show.empty and "item_id" in conv_show.columns:
        conv_show = conv_show[conv_show["item_id"].astype(str).str.strip() == str(selected_item_id).strip()].copy()
    return {"item_row": item_row, "base_unit": base_unit, "default_stock_unit": default_stock_unit, "default_order_unit": default_order_unit, "unit_price": unit_price, "price_unit": price_unit, "effective_date": effective_date, "base_unit_cost": base_unit_cost, "conv_show": conv_show}
