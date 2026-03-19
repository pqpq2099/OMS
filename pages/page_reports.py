# ============================================================
# ORIVIA OMS
# 檔案：pages/page_reports.py
# 說明：報表與分析頁
# 功能：顯示叫貨明細、進銷存分析、進貨分析與相關報表。
# 注意：這是分析層主頁，不應混入過多寫入邏輯。
# ============================================================

"""
頁面模組：報表與分析。
這個檔案負責：
1. 庫存歷史
2. 匯出頁
3. 進銷存分析
4. 成本檢查

如果之後要調整報表畫面或分析邏輯入口，優先看這個檔案。
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st
from oms_core import (
    PLOTLY_CONFIG,
    _build_inventory_history_summary_df,
    _build_latest_item_metrics_df,
    _build_purchase_detail_df,
    _build_purchase_summary_df,
    _clean_option_list,
    _get_active_df,
    _item_display_name,
    _norm,
    _parse_date,
    _safe_float,
    get_base_unit_cost,
    get_table_versions,
    read_table,
    render_report_dataframe,
    send_line_message,
)

# Plotly (optional)
try:
    import plotly.express as px

    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False


_REPORT_SHARED_TABLES = ("items", "vendors", "stores", "prices", "unit_conversions")


def _load_report_shared_tables() -> dict[str, pd.DataFrame]:
    """報表頁共用主資料，減少同頁多處重複 read_table。"""
    versions = get_table_versions(_REPORT_SHARED_TABLES)
    cache = st.session_state.get("_reports_shared_tables_cache")
    if isinstance(cache, dict) and cache.get("versions") == versions:
        data = cache.get("data", {})
        if data:
            return {k: v.copy() for k, v in data.items()}

    data = {name: read_table(name) for name in _REPORT_SHARED_TABLES}
    st.session_state["_reports_shared_tables_cache"] = {
        "versions": versions,
        "data": {k: v.copy() for k, v in data.items()},
    }
    return {k: v.copy() for k, v in data.items()}


def _clear_report_shared_tables_cache():
    st.session_state.pop("_reports_shared_tables_cache", None)


# ============================================================
# [B1] 歷史頁資料補強
# ============================================================
def _build_history_with_vendor(store_id: str, start_date: date, end_date: date):
    hist_df = _build_inventory_history_summary_df(
        store_id=store_id,
        start_date=start_date,
        end_date=end_date,
    )

    if hist_df.empty:
        return hist_df

    if "廠商" in hist_df.columns and hist_df["廠商"].astype(str).str.strip().ne("").any():
        return hist_df

    shared_tables = _load_report_shared_tables()
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
    vendors_map["廠商"] = vendors_map.apply(
        lambda r: _norm(r.get("vendor_name", "")) or _norm(r.get("vendor_id", "")) or "-",
        axis=1,
    )
    vendors_map = vendors_map[["vendor_id", "廠商"]].drop_duplicates()

    merged = hist_df.merge(
        items_map,
        on="item_id",
        how="left",
    )

    merged = merged.merge(
        vendors_map,
        left_on="default_vendor_id",
        right_on="vendor_id",
        how="left",
    )

    merged["廠商"] = merged["廠商"].fillna("-")

    for col in ["default_vendor_id", "vendor_id"]:
        if col in merged.columns:
            merged = merged.drop(columns=[col])

    return merged


# ============================================================
# [B2] 分析頁資料補強
# ============================================================
def _build_analysis_with_vendor(store_id: str, start_date: date, end_date: date):
    hist_df = _build_inventory_history_summary_df(
        store_id=store_id,
        start_date=start_date,
        end_date=end_date,
    )

    if hist_df.empty:
        return hist_df

    if "廠商" in hist_df.columns and hist_df["廠商"].astype(str).str.strip().ne("").any():
        return hist_df

    shared_tables = _load_report_shared_tables()
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
    vendors_map["廠商"] = vendors_map.apply(
        lambda r: _norm(r.get("vendor_name", "")) or _norm(r.get("vendor_id", "")) or "-",
        axis=1,
    )
    vendors_map = vendors_map[["vendor_id", "廠商"]].drop_duplicates()

    merged = hist_df.merge(
        items_map,
        on="item_id",
        how="left",
    )
    merged = merged.merge(
        vendors_map,
        left_on="default_vendor_id",
        right_on="vendor_id",
        how="left",
    )

    merged["廠商"] = merged["廠商"].fillna("-")

    for col in ["default_vendor_id", "vendor_id"]:
        if col in merged.columns:
            merged = merged.drop(columns=[col])

    return merged


def _short_item_name(text: str, max_len: int = 14) -> str:
    value = str(text or "").strip()
    if len(value) <= max_len:
        return value
    return value[:max_len] + "…"


def _display_mode_selector(key: str) -> str:
    return st.radio(
        "表格顯示模式",
        options=["手機精簡", "完整表格"],
        horizontal=True,
        key=key,
    )

def _get_store_scope_options():
    stores_df = _load_report_shared_tables()["stores"]
    if stores_df.empty or "store_id" not in stores_df.columns:
        fallback_id = str(st.session_state.get("store_id", "")).strip()
        fallback_name = str(st.session_state.get("store_name", fallback_id)).strip()
        return [fallback_id] if fallback_id else [], {fallback_id: fallback_name} if fallback_id else {}

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

    login_role = str(st.session_state.get("login_role_id", "")).strip()
    current_store_id = str(st.session_state.get("store_id", "")).strip()

    if login_role in ["owner", "admin"]:
        work = stores_df.sort_values([c for c in ["store_name_zh", "store_name", "store_id"] if c in stores_df.columns]).copy()
    else:
        work = stores_df[stores_df["store_id"] == current_store_id].copy()

    if work.empty and current_store_id:
        return [current_store_id], {current_store_id: str(st.session_state.get("store_name", current_store_id)).strip() or current_store_id}

    option_map = dict(zip(work["store_id"].tolist(), work["store_display"].tolist()))
    return list(option_map.keys()), option_map


def _select_export_store(key: str):
    store_ids, store_label_map = _get_store_scope_options()
    if not store_ids:
        return "", ""

    current_store_id = str(st.session_state.get("store_id", "")).strip()
    default_index = 0
    if current_store_id in store_ids:
        default_index = store_ids.index(current_store_id)

    selected_store_id = st.selectbox(
        "選擇分店",
        options=store_ids,
        index=default_index,
        format_func=lambda x: store_label_map.get(x, x),
        key=key,
    )
    return selected_store_id, store_label_map.get(selected_store_id, selected_store_id)


def _download_csv_block(preview: pd.DataFrame, filename: str):
    if preview.empty:
        st.info("💡 此條件下無可匯出資料")
        return

    st.download_button(
        "📥 匯出 CSV",
        preview.to_csv(index=False).encode("utf-8-sig"),
        file_name=filename,
        mime="text/csv",
        use_container_width=True,
        key=f"download_{filename}",
    )
    render_report_dataframe(preview)


def _format_mmdd_value(value):
    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return value
    return dt.strftime("%m/%d")


def _format_mmdd_column(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if df.empty or col not in df.columns:
        return df
    out = df.copy()
    out[col] = out[col].apply(_format_mmdd_value)
    return out



# ============================================================
# [R0] 庫存＋叫貨對照表（極簡版）
# 說明：
# 1. 只顯示單日資料
# 2. 欄位只保留：廠商 / 品項 / 這次庫存 / 這次叫貨
# 3. 只顯示庫存或叫貨非 0 的列
# ============================================================
def page_stock_order_compare():
    st.title("📄 庫存＋叫貨對照表")

    store_id = str(st.session_state.get("store_id", "")).strip()
    store_name = str(st.session_state.get("store_name", "")).strip()
    if not store_id:
        st.warning("請先選擇分店")
        return

    selected_date = st.date_input(
        "日期",
        value=st.session_state.get("record_date", date.today()),
        key="stock_order_compare_date",
    )

    latest_df = _build_latest_item_metrics_df(
        store_id=store_id,
        as_of_date=selected_date,
    )
    if latest_df.empty:
        st.info("這一天沒有可顯示的資料")
        return

    work = latest_df.copy()
    if "日期_dt" in work.columns:
        work = work[pd.to_datetime(work["日期_dt"], errors="coerce").dt.date == selected_date].copy()
    elif "日期" in work.columns:
        work = work[pd.to_datetime(work["日期"], errors="coerce").dt.date == selected_date].copy()

    if work.empty:
        st.info("這一天沒有可顯示的資料")
        return

    if "這次庫存" not in work.columns:
        work["這次庫存"] = 0
    if "這次叫貨" not in work.columns:
        work["這次叫貨"] = 0

    work["這次庫存"] = pd.to_numeric(work["這次庫存"], errors="coerce").fillna(0)
    work["這次叫貨"] = pd.to_numeric(work["這次叫貨"], errors="coerce").fillna(0)
    work = work[(work["這次庫存"] != 0) | (work["這次叫貨"] != 0)].copy()
    if work.empty:
        st.info("這一天沒有非 0 的庫存 / 叫貨資料")
        return

    items_df = read_table("items")
    vendors_df = read_table("vendors")

    stock_unit_map = {}
    order_unit_map = {}

    if not items_df.empty and "item_id" in items_df.columns:
        items_df = items_df.copy()
        items_df["item_id"] = items_df["item_id"].astype(str).str.strip()

        if "default_stock_unit" in items_df.columns:
            stock_unit_map = dict(
                zip(
                    items_df["item_id"],
                    items_df["default_stock_unit"].astype(str).str.strip(),
                )
            )

        if "default_order_unit" in items_df.columns:
            order_unit_map = dict(
                zip(
                    items_df["item_id"],
                    items_df["default_order_unit"].astype(str).str.strip(),
                )
            )

    if not vendors_df.empty and "vendor_id" in vendors_df.columns:
        vendors_df = vendors_df.copy()
        vendors_df["vendor_id"] = vendors_df["vendor_id"].astype(str).str.strip()
        vendors_df["vendor_name_disp"] = vendors_df.apply(
            lambda r: _norm(r.get("vendor_name_zh", "")) or _norm(r.get("vendor_name", "")) or _norm(r.get("vendor_id", "")) or "-",
            axis=1,
        )
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

    vendor_options = ["全部廠商"] + _clean_option_list(work["廠商"].dropna().tolist())
    selected_vendor = st.selectbox(
        "選擇廠商",
        vendor_options,
        index=0,
        key="stock_order_compare_vendor",
    )

    if selected_vendor != "全部廠商":
        work = work[work["廠商"].astype(str).str.strip() == selected_vendor].copy()

    work["庫存單位"] = work["item_id"].astype(str).str.strip().map(stock_unit_map).fillna("")
    work["叫貨單位"] = work["item_id"].astype(str).str.strip().map(order_unit_map).fillna("")

    item_col = "品項" if "品項" in work.columns else "item_id"
    preview = work[["廠商", item_col, "這次庫存", "庫存單位", "這次叫貨", "叫貨單位"]].copy()
    preview = preview.rename(columns={item_col: "品項"})

    preview["這次庫存"] = preview.apply(
        lambda r: f"{_safe_float(r['這次庫存']):g} {str(r['庫存單位']).strip()}".strip(),
        axis=1,
    )
    preview["這次叫貨"] = preview.apply(
        lambda r: f"{_safe_float(r['這次叫貨']):g} {str(r['叫貨單位']).strip()}".strip(),
        axis=1,
    )

    preview = preview.drop(columns=["庫存單位", "叫貨單位"])
    preview = preview.sort_values(["廠商", "品項"], ascending=[True, True]).reset_index(drop=True)

    if preview.empty:
        st.info("此條件下沒有可顯示的資料")
        return

    st.caption(f"{store_name}｜{selected_date.strftime('%m/%d')}")
    _download_csv_block(preview, f"stock_order_compare_{store_id}_{selected_date}.csv")

    if st.button("⬅️ 返回功能選單", use_container_width=True, key="back_from_stock_order_compare"):
        st.session_state.step = "select_vendor"
        st.rerun()


# ============================================================
# [R1] 庫存歷史頁
# ============================================================
def page_view_history():
    st.markdown(
        """
        <style>
        [data-testid='stMainBlockContainer'] {
            max-width: 95% !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        [data-testid='stDataFrame'] [role='gridcell'] {
            padding: 1px 2px !important;
            line-height: 1.0 !important;
        }
        [data-testid='stDataFrame'] [role='columnheader'] {
            padding: 2px 2px !important;
            font-size: 10px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title(f"📜 {st.session_state.store_name} 歷史叫貨紀錄")

    c_h_date1, c_h_date2 = st.columns(2)
    h_start = c_h_date1.date_input(
        "起始日期",
        value=date.today() - timedelta(days=30),
        key="hist_start_date",
    )
    h_end = c_h_date2.date_input(
        "結束日期",
        value=date.today(),
        key="hist_end_date",
    )

    hist_df = _build_history_with_vendor(
        store_id=st.session_state.store_id,
        start_date=h_start,
        end_date=h_end,
    )

    if hist_df.empty:
        st.info("💡 此區間內無紀錄。")
        if st.button("⬅️ 返回", use_container_width=True, key="back_hist_empty"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    vendor_values = (
        _clean_option_list(hist_df["廠商"].dropna().tolist())
        if "廠商" in hist_df.columns else []
    )
    all_v = ["全部廠商"] + vendor_values
    sel_v = st.selectbox(
        "🏢 選擇廠商",
        options=all_v,
        index=0,
        key="hist_vendor_filter",
    )

    shared_tables = _load_report_shared_tables()
    items_df = shared_tables["items"].copy()
    vendors_df = shared_tables["vendors"].copy()

    item_values = []

    if not items_df.empty:
        items_df.columns = [str(c).strip() for c in items_df.columns]
        items_df["item_id"] = items_df.get("item_id", "").astype(str).str.strip()
        items_df["default_vendor_id"] = items_df.get("default_vendor_id", "").astype(str).str.strip()

        def _hist_item_label(r):
            return (
                _norm(r.get("item_name_zh", ""))
                or _norm(r.get("item_name", ""))
                or _norm(r.get("item_id", ""))
            )

        items_df["品項顯示"] = items_df.apply(_hist_item_label, axis=1)

        if "is_active" in items_df.columns:
            items_df = items_df[
                items_df["is_active"].astype(str).str.strip().isin(["1", "True", "true", "YES", "yes", "是"])
            ].copy()

        if sel_v != "全部廠商" and not vendors_df.empty:
            vendors_df.columns = [str(c).strip() for c in vendors_df.columns]
            vendors_df["vendor_id"] = vendors_df.get("vendor_id", "").astype(str).str.strip()
            vendors_df["vendor_name_norm"] = vendors_df.apply(
                lambda r: _norm(r.get("vendor_name", "")) or _norm(r.get("vendor_id", "")),
                axis=1,
            )

            target_vendor = vendors_df[
                vendors_df["vendor_name_norm"].astype(str).str.strip() == str(sel_v).strip()
            ].copy()

            if not target_vendor.empty:
                target_vendor_id = str(target_vendor.iloc[0]["vendor_id"]).strip()
                items_df = items_df[
                    items_df["default_vendor_id"].astype(str).str.strip() == target_vendor_id
                ].copy()
            else:
                items_df = items_df.iloc[0:0].copy()

        item_values = _clean_option_list(items_df["品項顯示"].dropna().tolist())

    all_i = ["全部品項"] + item_values

    if "hist_vendor_filter_prev" not in st.session_state:
        st.session_state.hist_vendor_filter_prev = sel_v

    if st.session_state.hist_vendor_filter_prev != sel_v:
        st.session_state.hist_item_filter = "全部品項"
        st.session_state.hist_vendor_filter_prev = sel_v

    if st.session_state.get("hist_item_filter", "全部品項") not in all_i:
        st.session_state.hist_item_filter = "全部品項"

    sel_i = st.selectbox(
        "🏷️ 選擇品項",
        options=all_i,
        key="hist_item_filter",
    )

    filt_df = hist_df.copy()

    if sel_v != "全部廠商":
        filt_df = filt_df[filt_df["廠商"] == sel_v].copy()

    if sel_i != "全部品項":
        filt_df = filt_df[
            filt_df["品項"].astype(str).str.strip() == str(sel_i).strip()
        ].copy()

    detail_df = filt_df.copy()
    detail_df = detail_df[
        (detail_df["上次庫存"] != 0)
        | (detail_df["期間進貨"] != 0)
        | (detail_df["期間消耗"] != 0)
        | (detail_df["這次庫存"] != 0)
        | (detail_df.get("這次叫貨", 0) != 0)
    ].copy()

    if detail_df.empty:
        st.caption("此條件下無歷史資料")
    elif sel_v == "全部廠商":
        st.caption("全部廠商時，歷史叫貨紀錄明細預設不顯示")
    else:
        mode = _display_mode_selector("hist_display_mode")

        full_cols = [
            "日期顯示",
            "品項",
            "上次庫存",
            "期間進貨",
            "庫存合計",
            "這次庫存",
            "期間消耗",
            "這次叫貨",
            "日平均",
        ]
        export_df = detail_df[full_cols].copy().reset_index(drop=True)
        export_df = _format_mmdd_column(export_df, "日期顯示")

        if mode == "手機精簡":
            show_df = export_df[["日期顯示", "品項", "這次庫存", "這次叫貨", "日平均"]].copy()
            show_df["品項"] = show_df["品項"].apply(_short_item_name)
            cfg = {
                "日期顯示": st.column_config.TextColumn("日期", width="small"),
                "品項": st.column_config.TextColumn(width="medium"),
                "這次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                "這次叫貨": st.column_config.NumberColumn(format="%.1f", width="small"),
                "日平均": st.column_config.NumberColumn(format="%.1f", width="small"),
            }
        else:
            show_df = export_df.copy()
            cfg = {
                "日期顯示": st.column_config.TextColumn("日期", width="small"),
                "品項": st.column_config.TextColumn(width="medium"),
                "上次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                "期間進貨": st.column_config.NumberColumn(format="%.1f", width="small"),
                "庫存合計": st.column_config.NumberColumn(format="%.1f", width="small"),
                "這次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                "期間消耗": st.column_config.NumberColumn(format="%.1f", width="small"),
                "這次叫貨": st.column_config.NumberColumn(format="%.1f", width="small"),
                "日平均": st.column_config.NumberColumn(format="%.1f", width="small"),
            }

        st.download_button(
            "📥 匯出 CSV",
            export_df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{st.session_state.store_name}_歷史叫貨紀錄_{sel_v}_{h_start}_{h_end}.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_history_csv",
        )

        render_report_dataframe(show_df, column_config=cfg)

    if st.button("⬅️ 返回", use_container_width=True, key="back_hist_final"):
        st.session_state.step = "select_vendor"
        st.rerun()

def page_export():
    st.title("📤 資料匯出")

    export_type = st.selectbox(
        "匯出資料類型",
        ["今日進貨明細", "進銷存分析", "歷史叫貨紀錄"],
        key="export_type",
    )

    selected_store_id, selected_store_name = _select_export_store("export_store_id")
    if not selected_store_id:
        st.warning("⚠️ 目前沒有可匯出的分店資料")
        if st.button("⬅️ 返回選單", use_container_width=True, key="back_export_no_store"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    c1, c2 = st.columns(2)
    start = c1.date_input("起始日期", value=date.today() - timedelta(days=14), key="export_start")
    end = c2.date_input("結束日期", value=date.today(), key="export_end")

    vendor_options = ["全部廠商"]
    item_options = ["全部品項"]
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

        selected_vendor = st.selectbox("選擇廠商", vendor_options, key="export_vendor_po")
        selected_item = st.selectbox("選擇品項", item_options, key="export_item_po")

        if not df.empty and selected_vendor != "全部廠商":
            df = df[df["vendor_name_disp"].astype(str).str.strip() == selected_vendor].copy()
        if not df.empty and selected_item != "全部品項":
            df = df[df["item_name_disp"].astype(str).str.strip() == selected_item].copy()

        if not df.empty:
            preview = pd.DataFrame({
                "日期": pd.to_datetime(df[date_field], errors="coerce").dt.strftime("%m/%d"),
                "分店": selected_store_name,
                "廠商": df.get("vendor_name_disp", ""),
                "品項": df.get("item_name_disp", ""),
                "數量": pd.to_numeric(df.get("order_qty_num", 0), errors="coerce").fillna(0),
                "單位": df.get("order_unit_disp", ""),
                "金額": pd.to_numeric(df.get("amount_num", 0), errors="coerce").fillna(0),
            }).reset_index(drop=True)
        filename = f"今日進貨明細_{selected_store_name}_{start}_{end}.csv"

    elif export_type == "進銷存分析":
        df = _build_analysis_with_vendor(
            store_id=selected_store_id,
            start_date=start,
            end_date=end,
        )
        if not df.empty and "廠商" in df.columns:
            vendor_options += _clean_option_list(df["廠商"].dropna().tolist())
        if not df.empty and "品項" in df.columns:
            item_options += _clean_option_list(df["品項"].dropna().tolist())

        selected_vendor = st.selectbox("選擇廠商", vendor_options, key="export_vendor_analysis")
        selected_item = st.selectbox("選擇品項", item_options, key="export_item_analysis")

        if not df.empty and selected_vendor != "全部廠商":
            df = df[df["廠商"].astype(str).str.strip() == selected_vendor].copy()
        if not df.empty and selected_item != "全部品項":
            df = df[df["品項"].astype(str).str.strip() == selected_item].copy()

        if not df.empty:
            df = df[(df["上次庫存"] != 0) | (df["期間進貨"] != 0) | (df["期間消耗"] != 0) | (df["這次庫存"] != 0) | (df["這次叫貨"] != 0)].copy()
            preview = df[[c for c in ["日期", "廠商", "品項", "上次庫存", "期間進貨", "庫存合計", "這次庫存", "期間消耗", "這次叫貨", "日平均"] if c in df.columns]].copy().reset_index(drop=True)
            preview = _format_mmdd_column(preview, "日期")
        filename = f"進銷存分析_{selected_store_name}_{start}_{end}.csv"

    elif export_type == "歷史叫貨紀錄":
        df = _build_history_with_vendor(
            store_id=selected_store_id,
            start_date=start,
            end_date=end,
        )
        if not df.empty and "廠商" in df.columns:
            vendor_options += _clean_option_list(df["廠商"].dropna().tolist())
        if not df.empty and "品項" in df.columns:
            item_options += _clean_option_list(df["品項"].dropna().tolist())

        selected_vendor = st.selectbox("選擇廠商", vendor_options, key="export_vendor_history")
        selected_item = st.selectbox("選擇品項", item_options, key="export_item_history")

        if not df.empty and selected_vendor != "全部廠商":
            df = df[df["廠商"].astype(str).str.strip() == selected_vendor].copy()
        if not df.empty and selected_item != "全部品項":
            df = df[df["品項"].astype(str).str.strip() == selected_item].copy()

        if not df.empty:
            df = df[(df["上次庫存"] != 0) | (df["期間進貨"] != 0) | (df["期間消耗"] != 0) | (df["這次庫存"] != 0) | (df.get("這次叫貨", 0) != 0)].copy()
            preview = df[[c for c in ["日期顯示", "廠商", "品項", "上次庫存", "期間進貨", "庫存合計", "這次庫存", "期間消耗", "這次叫貨", "日平均"] if c in df.columns]].copy().reset_index(drop=True)
            if "日期顯示" in preview.columns:
                preview = preview.rename(columns={"日期顯示": "日期"})
            preview = _format_mmdd_column(preview, "日期")
        filename = f"歷史叫貨紀錄_{selected_store_name}_{start}_{end}.csv"

    else:
        po_df = _build_purchase_detail_df()
        ana_df = _build_analysis_with_vendor(
            store_id=selected_store_id,
            start_date=start,
            end_date=end,
        )
        hist_df = _build_history_with_vendor(
            store_id=selected_store_id,
            start_date=start,
            end_date=end,
        )

        po_count = 0
        ana_count = 0
        hist_count = 0

        if not po_df.empty:
            date_field = "delivery_date_dt" if "delivery_date_dt" in po_df.columns else "order_date_dt"
            po_df = po_df[po_df["store_id"].astype(str).str.strip() == str(selected_store_id).strip()].copy()
            po_df = po_df[(po_df[date_field].notna()) & (po_df[date_field] >= start) & (po_df[date_field] <= end)].copy()
            po_count = len(po_df)
        if not ana_df.empty:
            ana_df = ana_df[(ana_df["上次庫存"] != 0) | (ana_df["期間進貨"] != 0) | (ana_df["期間消耗"] != 0) | (ana_df["這次庫存"] != 0) | (ana_df["這次叫貨"] != 0)].copy()
            ana_count = len(ana_df)
        if not hist_df.empty:
            hist_df = hist_df[(hist_df["上次庫存"] != 0) | (hist_df["期間進貨"] != 0) | (hist_df["期間消耗"] != 0) | (hist_df["這次庫存"] != 0) | (hist_df.get("這次叫貨", 0) != 0)].copy()
            hist_count = len(hist_df)

        preview = pd.DataFrame([
            {"資料類型": "今日進貨明細", "筆數": po_count, "分店": selected_store_name, "起始日期": start, "結束日期": end},
            {"資料類型": "進銷存分析", "筆數": ana_count, "分店": selected_store_name, "起始日期": start, "結束日期": end},
            {"資料類型": "歷史叫貨紀錄", "筆數": hist_count, "分店": selected_store_name, "起始日期": start, "結束日期": end},
        ])
        filename = f"資料總覽_{selected_store_name}_{start}_{end}.csv"

    st.markdown("---")
    _download_csv_block(preview, filename)

    if st.button("⬅️ 返回選單", use_container_width=True, key="back_export_center"):
        st.session_state.step = "select_vendor"
        st.rerun()


# ============================================================
# [R3] 進銷存分析頁
# ============================================================
def page_analysis():
    st.title("📊 進銷存分析")

    c_date1, c_date2 = st.columns(2)
    start = c_date1.date_input(
        "起始日期",
        value=date.today() - timedelta(days=14),
        key="ana_start",
    )
    end = c_date2.date_input(
        "結束日期",
        value=date.today(),
        key="ana_end",
    )

    hist_df = _build_analysis_with_vendor(
        store_id=st.session_state.store_id,
        start_date=start,
        end_date=end,
    )
    po_detail_df = _build_purchase_detail_df()

    purchase_filt = pd.DataFrame()
    if not po_detail_df.empty:
        date_field = "delivery_date_dt" if "delivery_date_dt" in po_detail_df.columns else "order_date_dt"
        purchase_filt = po_detail_df[
            (po_detail_df["store_id"].astype(str).str.strip() == str(st.session_state.store_id).strip())
            & (po_detail_df[date_field].notna())
            & (po_detail_df[date_field] >= start)
            & (po_detail_df[date_field] <= end)
        ].copy()
        purchase_filt["日期"] = pd.to_datetime(
            purchase_filt[date_field], errors="coerce"
        ).dt.strftime("%m/%d")
        purchase_filt["廠商"] = purchase_filt["vendor_name_disp"].apply(lambda x: _norm(x) or "-")
        purchase_filt["進貨金額"] = pd.to_numeric(purchase_filt["amount_num"], errors="coerce").fillna(0)

    if hist_df.empty and purchase_filt.empty:
        st.warning(f"⚠️ 在 {start} 到 {end} 之間查無紀錄。")
        if st.button("⬅️ 返回選單", use_container_width=True, key="back_from_analysis_no_data"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    st.markdown("---")

    hist_filt = hist_df.copy()

    vendor_values = []
    if not hist_filt.empty and "廠商" in hist_filt.columns:
        vendor_values = _clean_option_list(hist_filt["廠商"].dropna().tolist())
    elif not purchase_filt.empty and "廠商" in purchase_filt.columns:
        vendor_values = _clean_option_list(purchase_filt["廠商"].dropna().tolist())

    all_vendors = ["全部廠商"] + vendor_values
    selected_vendor = st.selectbox(
        "🏢 選擇廠商",
        options=all_vendors,
        index=0,
        key="ana_vendor_filter",
    )

    if selected_vendor != "全部廠商":
        if not hist_filt.empty and "廠商" in hist_filt.columns:
            hist_filt = hist_filt[hist_filt["廠商"] == selected_vendor].copy()
        if not purchase_filt.empty and "廠商" in purchase_filt.columns:
            purchase_filt = purchase_filt[purchase_filt["廠商"] == selected_vendor].copy()

    display_mode = _display_mode_selector("analysis_display_mode")

    st.markdown("---")

    total_purchase_amount = 0.0
    if not purchase_filt.empty and "進貨金額" in purchase_filt.columns:
        total_purchase_amount = float(
            pd.to_numeric(purchase_filt["進貨金額"], errors="coerce").fillna(0).sum()
        )

    total_stock_amount = 0.0
    if not hist_filt.empty:
        work_stock = hist_filt.copy()

        if "這次庫存" not in work_stock.columns:
            work_stock["這次庫存"] = 0
        if "這次庫存_base_qty" not in work_stock.columns:
            work_stock["這次庫存_base_qty"] = 0

        shared_tables = _load_report_shared_tables()
        items_df = shared_tables["items"]
        prices_df = shared_tables["prices"]
        conversions_df = _get_active_df(shared_tables["unit_conversions"])

        work_stock["這次庫存"] = pd.to_numeric(
            work_stock["這次庫存"], errors="coerce"
        ).fillna(0)
        work_stock["這次庫存_base_qty"] = pd.to_numeric(
            work_stock["這次庫存_base_qty"], errors="coerce"
        ).fillna(0)

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

            base_unit_cost = get_base_unit_cost(
                item_id=item_id,
                target_date=target_date,
                items_df=items_df,
                prices_df=prices_df,
                conversions_df=conversions_df,
            )

            if base_unit_cost is None:
                return 0.0

            return round(base_qty * float(base_unit_cost), 2)

        work_stock["庫存總額"] = work_stock.apply(_calc_stock_amount, axis=1)
        total_stock_amount = float(
            pd.to_numeric(work_stock["庫存總額"], errors="coerce").fillna(0).sum()
        )

    c_amt1, c_amt2 = st.columns(2)
    c_amt1.metric("進貨總金額", f"{total_purchase_amount:,.1f}")
    c_amt2.metric("庫存總金額", f"{total_stock_amount:,.1f}")

    if selected_vendor == "全部廠商":
        st.subheader("📋 全部廠商金額統計")

        if purchase_filt.empty:
            st.info("目前沒有可顯示的金額資料")
        else:
            vendor_summary = (
                purchase_filt.groupby(["日期", "廠商"], as_index=False)["進貨金額"]
                .sum()
                .sort_values(["日期", "廠商"], ascending=[False, True])
                .reset_index(drop=True)
            )

            st.download_button(
                "📥 匯出 CSV",
                vendor_summary.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"進銷存分析_全部廠商_{start}_{end}.csv",
                mime="text/csv",
                use_container_width=False,
                key="download_analysis_all_vendors",
            )

            show_vendor_summary = vendor_summary.copy()
            show_vendor_summary = _format_mmdd_column(show_vendor_summary, "日期")
            if display_mode == "手機精簡":
                show_vendor_summary["廠商"] = show_vendor_summary["廠商"].apply(lambda x: _short_item_name(x, 10))

            render_report_dataframe(
                show_vendor_summary,
                column_config={
                    "日期": st.column_config.TextColumn(width="small"),
                    "廠商": st.column_config.TextColumn(width="medium"),
                    "進貨金額": st.column_config.NumberColumn(format="%.1f", width="small"),
                },
            )

        if st.button("⬅️ 返回選單", use_container_width=True, key="back_from_analysis_all"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    st.subheader(f"📦 {selected_vendor} 品項明細")

    if hist_filt.empty:
        st.info("此廠商在目前條件下無資料")
    else:
        detail_df = hist_filt.copy()

        if "日期" in detail_df.columns:
            if pd.api.types.is_numeric_dtype(detail_df["日期"]):
                detail_df["日期"] = pd.to_datetime(
                    detail_df["日期"], unit="s", errors="coerce"
                ).dt.strftime("%m/%d")
            else:
                detail_df["日期"] = pd.to_datetime(
                    detail_df["日期"], errors="coerce"
                ).dt.strftime("%m/%d")

        detail_df = detail_df[
            (detail_df["上次庫存"] != 0)
            | (detail_df["期間進貨"] != 0)
            | (detail_df["期間消耗"] != 0)
            | (detail_df["這次庫存"] != 0)
            | (detail_df["這次叫貨"] != 0)
        ].copy()

        if detail_df.empty:
            st.caption("此廠商在目前條件下無品項資料")
        else:
            show_cols = [
                "日期",
                "品項",
                "上次庫存",
                "期間進貨",
                "庫存合計",
                "這次庫存",
                "期間消耗",
                "這次叫貨",
                "日平均",
            ]

            export_df = detail_df[show_cols].copy().reset_index(drop=True)
            export_df = _format_mmdd_column(export_df, "日期")

            if display_mode == "手機精簡":
                show_df = export_df[["日期", "品項", "這次庫存", "這次叫貨", "日平均"]].copy()
                show_df["品項"] = show_df["品項"].apply(_short_item_name)
                cfg = {
                    "日期": st.column_config.TextColumn(width="small"),
                    "品項": st.column_config.TextColumn(width="medium"),
                    "這次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "這次叫貨": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "日平均": st.column_config.NumberColumn(format="%.1f", width="small"),
                }
            else:
                show_df = export_df.copy()
                cfg = {
                    "日期": st.column_config.TextColumn(width="small"),
                    "品項": st.column_config.TextColumn(width="medium"),
                    "上次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "期間進貨": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "庫存合計": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "這次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "期間消耗": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "這次叫貨": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "日平均": st.column_config.NumberColumn(format="%.1f", width="small"),
                }

            st.download_button(
                "📥 匯出 CSV",
                export_df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"進銷存分析_{selected_vendor}_{start}_{end}.csv",
                mime="text/csv",
                use_container_width=False,
                key="download_analysis_single_vendor",
            )

            render_report_dataframe(show_df, column_config=cfg)

    if st.button("⬅️ 返回選單", use_container_width=True, key="back_from_analysis_single"):
        st.session_state.step = "select_vendor"
        st.rerun()

def page_cost_debug():
    st.title("🧮 成本檢查")

    shared_tables = _load_report_shared_tables()
    items_df = _get_active_df(shared_tables["items"])
    prices_df = shared_tables["prices"]
    conversions_df = _get_active_df(shared_tables["unit_conversions"])

    if items_df.empty:
        st.warning("⚠️ items 資料讀取失敗")
        if st.button("⬅️ 返回選單", use_container_width=True, key="back_from_cost_debug_empty"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    work = items_df.copy()
    work["item_label"] = work.apply(
        lambda r: f"{_item_display_name(r)} ({_norm(r.get('item_id', ''))})",
        axis=1,
    )
    work = work.sort_values("item_label")

    item_options = work["item_id"].astype(str).tolist()

    selected_item_id = st.selectbox(
        "選擇品項",
        options=item_options,
        format_func=lambda x: work.loc[work["item_id"] == x, "item_label"].iloc[0],
        key="cost_debug_item_id",
    )

    target_date = st.date_input(
        "查詢日期",
        value=st.session_state.record_date,
        key="cost_debug_date",
    )

    item_row = work[
        work["item_id"].astype(str).str.strip() == str(selected_item_id).strip()
    ].iloc[0]

    base_unit = _norm(item_row.get("base_unit", ""))
    default_stock_unit = _norm(item_row.get("default_stock_unit", ""))
    default_order_unit = _norm(item_row.get("default_order_unit", ""))

    price_rows = prices_df.copy()
    if not price_rows.empty and "item_id" in price_rows.columns:
        price_rows = price_rows[
            price_rows["item_id"].astype(str).str.strip() == str(selected_item_id).strip()
        ].copy()

        if "is_active" in price_rows.columns:
            price_rows = price_rows[
                price_rows["is_active"].apply(
                    lambda x: str(x).strip() in ["1", "True", "true", "YES", "yes", "是"]
                )
            ].copy()

        if "effective_date" in price_rows.columns:
            price_rows["__eff"] = price_rows["effective_date"].apply(
                lambda x: None if str(x).strip() == "" else __import__("pandas").to_datetime(x).date()
            )
        else:
            price_rows["__eff"] = None

        if "end_date" in price_rows.columns:
            price_rows["__end"] = price_rows["end_date"].apply(
                lambda x: None if str(x).strip() == "" else __import__("pandas").to_datetime(x).date()
            )
        else:
            price_rows["__end"] = None

        price_rows = price_rows[
            (price_rows["__eff"].isna() | (price_rows["__eff"] <= target_date))
            & (price_rows["__end"].isna() | (price_rows["__end"] >= target_date))
        ].copy()

        if not price_rows.empty:
            price_rows = price_rows.sort_values("__eff", ascending=True)
            latest_price = price_rows.iloc[-1]
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

    base_unit_cost = get_base_unit_cost(
        item_id=selected_item_id,
        target_date=target_date,
        items_df=items_df,
        prices_df=prices_df,
        conversions_df=conversions_df,
    )

    st.markdown("---")
    st.subheader("檢查結果")
    st.write(f"**品項名稱：** {_item_display_name(item_row)}")
    st.write(f"**基準單位：** {base_unit or '未設定'}")
    st.write(f"**預設庫存單位：** {default_stock_unit or '未設定'}")
    st.write(f"**預設叫貨單位：** {default_order_unit or '未設定'}")
    st.write(f"**價格：** {unit_price}")
    st.write(f"**價格單位：** {price_unit or '未設定'}")
    st.write(f"**價格生效日：** {effective_date or '未設定'}")
    st.write(f"**基準單位成本：** {base_unit_cost if base_unit_cost is not None else '無法計算'}")

    st.markdown("---")
    st.subheader("換算規則")

    conv_show = conversions_df.copy()
    if not conv_show.empty and "item_id" in conv_show.columns:
        conv_show = conv_show[
            conv_show["item_id"].astype(str).str.strip() == str(selected_item_id).strip()
        ].copy()

    if conv_show.empty:
        st.caption("此品項目前沒有換算規則")
    else:
        show_cols = [
            c
            for c in ["conversion_id", "from_unit", "to_unit", "ratio", "is_active"]
            if c in conv_show.columns
        ]
        render_report_dataframe(conv_show[show_cols])

    if st.button("⬅️ 返回選單", use_container_width=True, key="back_from_cost_debug"):
        st.session_state.step = "select_vendor"
        st.rerun()
