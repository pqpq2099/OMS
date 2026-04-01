from __future__ import annotations

from datetime import date

import pandas as pd

from shared.services import service_order_core
from shared.utils.utils_units import convert_unit
from operations.logic.order_query_common import load_order_page_tables


def convert_metric_base_to_stock_display_qty(
    *,
    item_id: str,
    qty: float,
    stock_unit: str,
    base_unit: str,
    conversions_df: pd.DataFrame,
    as_of_date: date,
) -> float:
    qty = service_order_core.safe_float(qty, 0)
    item_id = service_order_core.norm(item_id)
    stock_unit = service_order_core.norm(stock_unit)
    base_unit = service_order_core.norm(base_unit)

    if not item_id or not stock_unit:
        return round(qty, 1)

    if qty == 0 or stock_unit == base_unit or not base_unit:
        return round(qty, 1)

    try:
        converted = convert_unit(
            item_id=item_id,
            qty=qty,
            from_unit=base_unit,
            to_unit=stock_unit,
            conversions_df=conversions_df,
            as_of_date=as_of_date,
        )
        return round(converted, 1)
    except Exception:
        return round(qty, 1)


def build_daily_stock_order_record_view_model(*, store_id: str, store_name: str, selected_date: date) -> dict:
    page_tables = load_order_page_tables()
    vendors_df = service_order_core.get_active_df(page_tables["vendors"])
    items_df = service_order_core.get_active_df(page_tables["items"])
    stocktakes_df = page_tables["stocktakes"]
    stocktake_lines_df = page_tables["stocktake_lines"]
    po_df = page_tables["purchase_orders"]
    pol_df = page_tables["purchase_order_lines"]

    if vendors_df.empty or items_df.empty:
        return {"status": "warning", "message": "⚠️ 廠商或品項資料讀取失敗"}

    item_vendor_ids = set(items_df.get("default_vendor_id", pd.Series(dtype=str)).astype(str).str.strip())
    vendors = vendors_df[vendors_df["vendor_id"].astype(str).str.strip().isin(item_vendor_ids)].copy()
    if vendors.empty:
        return {"status": "info", "message": "目前沒有可用廠商"}

    vendors["vendor_label"] = vendors.apply(service_order_core.label_vendor, axis=1)
    vendors = vendors.sort_values(by=["vendor_label"], ascending=True).reset_index(drop=True)

    vendor_options = [
        {
            "vendor_id": service_order_core.norm(r.get("vendor_id", "")),
            "vendor_label": r.get("vendor_label", ""),
        }
        for _, r in vendors.iterrows()
    ]

    latest_metrics_df = service_order_core.build_latest_item_metrics_df(
        store_id=store_id,
        as_of_date=selected_date,
    )

    latest_metrics_map = {}
    if not latest_metrics_df.empty:
        latest_metrics_df = latest_metrics_df.copy()
        if "vendor_id" in latest_metrics_df.columns:
            latest_metrics_df["vendor_id"] = latest_metrics_df["vendor_id"].astype(str).str.strip()
        for _, m in latest_metrics_df.iterrows():
            latest_metrics_map[service_order_core.norm(m.get("item_id", ""))] = m.to_dict()

    return {
        "status": "ok",
        "page_tables": page_tables,
        "vendor_options": vendor_options,
        "latest_metrics_map": latest_metrics_map,
        "store_name": store_name,
        "selected_date": selected_date,
        "po_df": po_df,
        "pol_df": pol_df,
        "stocktakes_df": stocktakes_df,
        "stocktake_lines_df": stocktake_lines_df,
        "items_df": items_df,
    }


def build_vendor_daily_record_rows(
    *,
    page_tables: dict[str, pd.DataFrame],
    items_df: pd.DataFrame,
    po_df: pd.DataFrame,
    pol_df: pd.DataFrame,
    stocktakes_df: pd.DataFrame,
    stocktake_lines_df: pd.DataFrame,
    latest_metrics_map: dict,
    store_id: str,
    vendor_id: str,
    selected_date: date,
) -> dict:
    vendor_items = items_df[
        items_df["default_vendor_id"].astype(str).str.strip() == vendor_id
    ].copy()

    if vendor_items.empty:
        return {"status": "info", "message": "此廠商目前沒有對應品項"}

    vendor_items = service_order_core.sort_items_for_operation(vendor_items).reset_index(drop=True)

    po_work = po_df.copy()
    if not po_work.empty:
        po_work["store_id"] = po_work["store_id"].astype(str).str.strip()
        po_work["vendor_id"] = po_work["vendor_id"].astype(str).str.strip()
        po_work["order_date_dt"] = pd.to_datetime(po_work.get("order_date"), errors="coerce")
        po_work["created_at_dt"] = pd.to_datetime(po_work.get("created_at"), errors="coerce")
        po_work = po_work[
            (po_work["store_id"] == store_id)
            & (po_work["vendor_id"] == vendor_id)
            & (po_work["order_date_dt"].dt.date == selected_date)
        ].copy()

    latest_po_id = ""
    if not po_work.empty:
        sort_cols = [c for c in ["created_at_dt", "order_date_dt"] if c in po_work.columns]
        if sort_cols:
            po_work = po_work.sort_values(sort_cols, ascending=True)
        latest_po = po_work.tail(1).iloc[0]
        latest_po_id = service_order_core.norm(latest_po.get("po_id", ""))

    order_map = {}
    if latest_po_id and not pol_df.empty:
        pol_work = pol_df.copy()
        pol_work["po_id"] = pol_work["po_id"].astype(str).str.strip()
        pol_work = pol_work[pol_work["po_id"] == latest_po_id].copy()
        for _, r in pol_work.iterrows():
            item_id = service_order_core.norm(r.get("item_id", ""))
            if not item_id:
                continue
            order_map[item_id] = {
                "order_qty": service_order_core.safe_float(r.get("order_qty", 0)),
                "order_unit": service_order_core.norm(r.get("order_unit", "")),
            }

    stocktake_map = {}
    if not stocktakes_df.empty and not stocktake_lines_df.empty:
        st_work = stocktakes_df.copy()
        stl_work = stocktake_lines_df.copy()

        if "stocktake_id" in st_work.columns and "stocktake_id" in stl_work.columns:
            st_work["stocktake_id"] = st_work["stocktake_id"].astype(str).str.strip()
            st_work["store_id"] = st_work.get("store_id", "").astype(str).str.strip()
            st_work["vendor_id"] = st_work.get("vendor_id", "").astype(str).str.strip()
            st_work["stocktake_date_dt"] = pd.to_datetime(st_work.get("stocktake_date"), errors="coerce")
            st_work["created_at_dt"] = pd.to_datetime(st_work.get("created_at"), errors="coerce")

            stl_work["stocktake_id"] = stl_work["stocktake_id"].astype(str).str.strip()
            stl_work["store_id"] = stl_work.get("store_id", "").astype(str).str.strip()
            stl_work["vendor_id"] = stl_work.get("vendor_id", "").astype(str).str.strip()
            stl_work["item_id"] = stl_work.get("item_id", "").astype(str).str.strip()
            stl_work["created_at_dt"] = pd.to_datetime(stl_work.get("created_at"), errors="coerce")

            st_work = st_work[
                (st_work["store_id"] == store_id)
                & (st_work["stocktake_date_dt"].dt.date == selected_date)
            ].copy()

            if not st_work.empty:
                exact_st = st_work[st_work["vendor_id"] == vendor_id].copy()
                candidate_stocktake_ids = set()
                if not exact_st.empty:
                    candidate_stocktake_ids = set(exact_st["stocktake_id"].tolist())
                else:
                    same_day_ids = set(st_work["stocktake_id"].tolist())
                    stl_same_day = stl_work[stl_work["stocktake_id"].isin(same_day_ids)].copy()
                    if not stl_same_day.empty:
                        stl_same_day = stl_same_day[
                            (stl_same_day["store_id"] == store_id)
                            & (stl_same_day["vendor_id"] == vendor_id)
                        ].copy()
                        candidate_stocktake_ids = set(stl_same_day["stocktake_id"].tolist())

                if candidate_stocktake_ids:
                    stl_pick = stl_work[stl_work["stocktake_id"].isin(candidate_stocktake_ids)].copy()
                    stl_pick = stl_pick[
                        (stl_pick["store_id"] == store_id)
                        & (stl_pick["vendor_id"] == vendor_id)
                    ].copy()
                    if stl_pick.empty:
                        stl_pick = stl_work[stl_work["stocktake_id"].isin(candidate_stocktake_ids)].copy()
                    if not stl_pick.empty:
                        meta_cols = [c for c in ["stocktake_id", "stocktake_date_dt", "created_at_dt"] if c in st_work.columns]
                        stl_pick = stl_pick.merge(
                            st_work[meta_cols].drop_duplicates(subset=["stocktake_id"]),
                            on="stocktake_id",
                            how="left",
                            suffixes=("", "_main"),
                        )
                        if "created_at_dt_main" in stl_pick.columns:
                            stl_pick["sort_created_at"] = stl_pick["created_at_dt_main"]
                        else:
                            stl_pick["sort_created_at"] = stl_pick["created_at_dt"]
                        if "stocktake_date_dt" not in stl_pick.columns:
                            stl_pick["stocktake_date_dt"] = pd.NaT
                        stl_pick = stl_pick.sort_values(
                            by=["sort_created_at", "stocktake_date_dt"],
                            ascending=True,
                            na_position="last",
                        )
                        latest_by_item = stl_pick.drop_duplicates(subset=["item_id"], keep="last")
                        for _, r in latest_by_item.iterrows():
                            item_id = service_order_core.norm(r.get("item_id", ""))
                            if not item_id:
                                continue
                            stock_qty = r.get("stock_qty", r.get("qty", 0))
                            stock_unit = r.get("stock_unit", r.get("unit_id", ""))
                            stocktake_map[item_id] = {
                                "stock_qty": service_order_core.safe_float(stock_qty),
                                "stock_unit": service_order_core.norm(stock_unit),
                            }

    if not order_map and not stocktake_map:
        return {"status": "info", "message": "這一天目前沒有找到庫存 / 叫貨紀錄。"}

    conversions_df = page_tables["unit_conversions"] if "unit_conversions" in page_tables else pd.DataFrame()
    latest_metrics_vendor_map = {}
    for item_id, metric in latest_metrics_map.items():
        if service_order_core.norm(metric.get("vendor_id", "")) == str(vendor_id).strip():
            latest_metrics_vendor_map[item_id] = metric

    rows = []
    for _, row in vendor_items.iterrows():
        item_id = service_order_core.norm(row.get("item_id", ""))
        item_name = service_order_core.item_display_name(row)

        base_unit = service_order_core.norm(row.get("base_unit", ""))
        stock_unit_default = service_order_core.norm(row.get("default_stock_unit", "")) or base_unit
        order_unit_default = service_order_core.norm(row.get("default_order_unit", "")) or base_unit

        metric = latest_metrics_vendor_map.get(item_id, {})
        total_stock_ref = service_order_core.safe_float(metric.get("庫存合計", 0))
        daily_avg = service_order_core.safe_float(metric.get("日平均", 0))
        suggest_qty = round(daily_avg * 1.5, 1)
        status_hint = service_order_core.norm(service_order_core.status_hint(total_stock_ref, daily_avg, suggest_qty))

        total_stock_display = convert_metric_base_to_stock_display_qty(
            item_id=item_id,
            qty=total_stock_ref,
            stock_unit=stock_unit_default,
            base_unit=base_unit,
            conversions_df=conversions_df,
            as_of_date=selected_date,
        )
        suggest_display = convert_metric_base_to_stock_display_qty(
            item_id=item_id,
            qty=suggest_qty,
            stock_unit=stock_unit_default,
            base_unit=base_unit,
            conversions_df=conversions_df,
            as_of_date=selected_date,
        )

        stock_info = stocktake_map.get(item_id, {})
        order_info = order_map.get(item_id, {})

        rows.append({
            "item_id": item_id,
            "item_name": item_name,
            "status_hint": status_hint,
            "stock_display": total_stock_display,
            "suggest_display": suggest_display,
            "stock_unit_default": stock_unit_default,
            "stock_qty": service_order_core.safe_float(stock_info.get("stock_qty", 0)),
            "stock_unit": service_order_core.norm(stock_info.get("stock_unit", "")) or stock_unit_default,
            "order_qty": service_order_core.safe_float(order_info.get("order_qty", 0)),
            "order_unit": service_order_core.norm(order_info.get("order_unit", "")) or order_unit_default,
        })

    return {
        "status": "ok",
        "rows": rows,
    }
