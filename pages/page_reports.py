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
    _build_purchase_detail_df,
    _build_purchase_summary_df,
    _clean_option_list,
    _get_active_df,
    _item_display_name,
    _norm,
    _parse_date,
    _safe_float,
    get_base_unit_cost,
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

    if "廠商" in hist_df.columns:
        return hist_df

    items_df = read_table("items")
    vendors_df = read_table("vendors")

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

    if "廠商" in hist_df.columns:
        return hist_df

    items_df = read_table("items")
    vendors_df = read_table("vendors")

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


def _short_item_name(text: str, limit: int = 14) -> str:
    value = str(text or '').strip()
    if len(value) <= limit:
        return value
    return value[:limit] + '…'


def _report_mode_key(section_key: str) -> str:
    return f"{section_key}_report_mode"


def _render_report_mode_selector(section_key: str, title: str = "顯示模式") -> str:
    return st.radio(
        title,
        options=["手機精簡", "完整表格"],
        horizontal=True,
        key=_report_mode_key(section_key),
    )


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

    st.title(f"📜 {st.session_state.store_name} 歷史紀錄")

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

    items_df = read_table("items").copy()
    vendors_df = read_table("vendors").copy()

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

    report_mode = _render_report_mode_selector("history", "歷史顯示模式")

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
        st.caption("全部廠商時，歷史紀錄明細預設不顯示")
    else:
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

        st.download_button(
            "📥 匯出 CSV",
            export_df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{st.session_state.store_name}_歷史紀錄_{sel_v}_{h_start}_{h_end}.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_history_csv",
        )

        if report_mode == "手機精簡":
            show_df = export_df.copy()
            show_df["品項"] = show_df["品項"].apply(_short_item_name)
            show_df = show_df[["日期顯示", "品項", "這次庫存", "這次叫貨", "日平均"]]
            show_config = {
                "日期顯示": st.column_config.TextColumn("日期", width="small"),
                "品項": st.column_config.TextColumn(width="medium"),
                "這次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                "這次叫貨": st.column_config.NumberColumn(format="%.1f", width="small"),
                "日平均": st.column_config.NumberColumn(format="%.1f", width="small"),
            }
        else:
            show_df = export_df
            show_config = {
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

        render_report_dataframe(show_df, column_config=show_config, height=360)

    if st.button("⬅️ 返回", use_container_width=True, key="back_hist_final"):
        st.session_state.step = "select_vendor"
        st.rerun()


# ============================================================
# [R2] 匯出頁
# ============================================================
def page_export():
    st.title("📋 今日進貨明細")

    po_df = _build_purchase_detail_df()

    week_map = {0: "一", 1: "二", 2: "三", 3: "四", 4: "五", 5: "六", 6: "日"}
    delivery_date = st.session_state.record_date + timedelta(days=1)
    header_date = f"{delivery_date.month}/{delivery_date.day}({week_map[delivery_date.weekday()]})"

    if po_df.empty:
        st.info("💡 尚無叫貨資料")
        if st.button("⬅️ 返回選單", use_container_width=True, key="back_to_vendor_export_empty"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    recs = po_df[
        (po_df["store_id"].astype(str).str.strip() == str(st.session_state.store_id).strip())
        & (po_df["order_date_dt"] == st.session_state.record_date)
        & (po_df["order_qty_num"] > 0)
    ].copy()

    if recs.empty:
        st.info("💡 今日尚無叫貨紀錄")
        if st.button("⬅️ 返回選單", use_container_width=True, key="back_to_vendor_export_nodata"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    store_name = st.session_state.store_name
    output = f"{store_name}\n{header_date}\n"

    vendor_order = (
        recs.groupby(["vendor_id", "vendor_name_disp"], as_index=False)["amount_num"]
        .sum()
        .sort_values("vendor_name_disp")
    )

    for _, v in vendor_order.iterrows():
        vendor_id = _norm(v.get("vendor_id", ""))
        vendor_name = _norm(v.get("vendor_name_disp", "")) or "未指定"

        output += f"\n{vendor_name}\n{store_name}\n"

        vendor_rows = recs[recs["vendor_id"].astype(str).str.strip() == vendor_id].copy()
        vendor_rows = vendor_rows.sort_values("item_name_disp")

        for _, r in vendor_rows.iterrows():
            qty = float(r["order_qty_num"])
            qty_display = int(qty) if qty.is_integer() else qty
            output += f"{r['item_name_disp']} {qty_display} {r['order_unit_disp']}\n"

        output += f"禮拜{week_map[delivery_date.weekday()]}到，謝謝\n"

    st.text_area("📱 LINE 訊息內容預覽", value=output, height=350)

    if st.button("🚀 直接發送明細至 LINE", type="primary", use_container_width=True):
        if send_line_message(output):
            st.success(f"✅ 已成功推送到 {store_name} 群組！")
        else:
            st.error("❌ 發送失敗，請檢查 LINE 設定。")

    if st.button("⬅️ 返回選單", use_container_width=True, key="back_to_vendor_export"):
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
        purchase_filt = po_detail_df[
            (po_detail_df["store_id"].astype(str).str.strip() == str(st.session_state.store_id).strip())
            & (po_detail_df["order_date_dt"].notna())
            & (po_detail_df["order_date_dt"] >= start)
            & (po_detail_df["order_date_dt"] <= end)
        ].copy()
        purchase_filt["日期"] = pd.to_datetime(
            purchase_filt["order_date_dt"], errors="coerce"
        ).dt.strftime("%Y/%m/%d")
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

    report_mode = _render_report_mode_selector("analysis", "分析顯示模式")

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
    
        items_df = read_table("items")
        prices_df = read_table("prices")
        conversions_df = _get_active_df(read_table("unit_conversions"))
    
        work_stock["這次庫存"] = pd.to_numeric(
            work_stock["這次庫存"], errors="coerce"
        ).fillna(0)
    
        def _calc_stock_amount(row):
            item_id = _norm(row.get("item_id", ""))
            qty = _safe_float(row.get("這次庫存", 0))
            row_date = row.get("日期")
    
            if not item_id or qty == 0:
                return 0.0
    
            target_date = _parse_date(row_date)
            if target_date is None:
                return 0.0
    
            base_unit_cost = get_base_unit_cost(
                item_id=item_id,
                target_date=target_date,
                items_df=items_df,
                prices_df=prices_df,
                conversions_df=conversions_df,
            )
    
            if base_unit_cost is None:
                return 0.0
    
            return round(qty * float(base_unit_cost), 2)
    
        work_stock["庫存總額"] = work_stock.apply(_calc_stock_amount, axis=1)
        total_stock_amount = float(
            pd.to_numeric(work_stock["庫存總額"], errors="coerce").fillna(0).sum()
        )
        def _calc_stock_amount(row):
            item_id = _norm(row.get("item_id", ""))
            qty = _safe_float(row.get("這次庫存", 0))
            row_date = row.get("日期")

            if not item_id or qty == 0:
                return 0.0

            target_date = _parse_date(row_date)
            if target_date is None:
                return 0.0

            base_unit_cost = get_base_unit_cost(
                item_id=item_id,
                target_date=target_date,
                items_df=items_df,
                prices_df=prices_df,
                conversions_df=conversions_df,
            )

            if base_unit_cost is None:
                return 0.0

            return round(qty * float(base_unit_cost), 2)

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

            render_report_dataframe(
                vendor_summary,
                column_config={
                    "日期": st.column_config.TextColumn(width="small"),
                    "廠商": st.column_config.TextColumn(width="medium"),
                    "進貨金額": st.column_config.NumberColumn(format="%.1f", width="small"),
                },
                height=360,
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
                ).dt.strftime("%Y/%m/%d")
            else:
                detail_df["日期"] = pd.to_datetime(
                    detail_df["日期"], errors="coerce"
                ).dt.strftime("%Y/%m/%d")

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

            st.download_button(
                "📥 匯出 CSV",
                export_df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"進銷存分析_{selected_vendor}_{start}_{end}.csv",
                mime="text/csv",
                use_container_width=False,
                key="download_analysis_single_vendor",
            )

            if report_mode == "手機精簡":
                show_df = export_df.copy()
                show_df["品項"] = show_df["品項"].apply(_short_item_name)
                show_df = show_df[["日期", "品項", "這次庫存", "這次叫貨", "日平均"]]
                show_config = {
                    "日期": st.column_config.TextColumn(width="small"),
                    "品項": st.column_config.TextColumn(width="medium"),
                    "這次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "這次叫貨": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "日平均": st.column_config.NumberColumn(format="%.1f", width="small"),
                }
            else:
                show_df = export_df
                show_config = {
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

            render_report_dataframe(show_df, column_config=show_config, height=360)

    if st.button("⬅️ 返回選單", use_container_width=True, key="back_from_analysis_single"):
        st.session_state.step = "select_vendor"
        st.rerun()


# ============================================================
# [R4] 成本檢查頁
# ============================================================
def page_cost_debug():
    if str(st.session_state.get("login_role_id", "")).strip().lower() not in ["owner", "admin"]:
        st.error("你沒有權限進入此頁。")
        return

    st.title("🧮 成本檢查")

    items_df = _get_active_df(read_table("items"))
    prices_df = read_table("prices")
    conversions_df = _get_active_df(read_table("unit_conversions"))

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
