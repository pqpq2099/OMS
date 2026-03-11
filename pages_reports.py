from __future__ import annotations

# ============================================================
# [A1] 基本匯入
# 這一區放：日期、Streamlit、核心函式
# ============================================================
from datetime import date, timedelta

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
# 這一區放：把歷史摘要補上廠商欄位
# 說明：
# 直接依照 item_id -> items.default_vendor_id -> vendors.vendor_name 來補
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
# 這一區放：把進銷存分析摘要補上廠商欄位
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
# ============================================================
# [E4] View History
# 這一區放：歷史紀錄頁
# 說明：
# 1. 只保留明細，不顯示趨勢
# 2. 提供外部 CSV 匯出按鈕
# 3. 保留返回按鈕
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

    vendor_values = _clean_option_list(hist_df["廠商"].dropna().tolist()) if "廠商" in hist_df.columns else []
    all_v = ["全部廠商"] + vendor_values
    sel_v = st.selectbox("🏢 選擇廠商", options=all_v, index=0, key="hist_vendor_filter")

    item_values = _clean_option_list(hist_df["品項"].dropna().tolist())
    all_i = ["全部品項"] + item_values
    sel_i = st.selectbox("🏷️ 選擇品項", options=all_i, index=0, key="hist_item_filter")

    filt_df = hist_df.copy()

    if sel_v != "全部廠商":
        filt_df = filt_df[filt_df["廠商"] == sel_v].copy()

    if sel_i != "全部品項":
        filt_df = filt_df[filt_df["品項"] == sel_i].copy()

    show_cols = [
        "日期顯示",
        "廠商",
        "品項",
        "上次庫存",
        "期間進貨",
        "庫存合計",
        "這次庫存",
        "期間消耗",
        "日平均",
    ]

    detail_df = filt_df.copy()
    detail_df = detail_df[
        (detail_df["上次庫存"] != 0)
        | (detail_df["期間進貨"] != 0)
        | (detail_df["期間消耗"] != 0)
        | (detail_df["這次庫存"] != 0)
    ].copy()

    if detail_df.empty:
        st.caption("此條件下無歷史資料")
    else:
        export_df = detail_df[show_cols].copy().reset_index(drop=True)

        st.download_button(
            "📥 匯出 CSV",
            export_df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{st.session_state.store_name}_歷史紀錄_{h_start}_{h_end}.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_history_csv",
        )

        render_report_dataframe(
            export_df,
            column_config={
                "日期顯示": st.column_config.TextColumn("日期", width="small"),
                "廠商": st.column_config.TextColumn(width="small"),
                "品項": st.column_config.TextColumn(width="small"),
                "上次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                "期間進貨": st.column_config.NumberColumn(format="%.1f", width="small"),
                "庫存合計": st.column_config.NumberColumn(format="%.1f", width="small"),
                "這次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                "期間消耗": st.column_config.NumberColumn(format="%.1f", width="small"),
                "日平均": st.column_config.NumberColumn(format="%.1f", width="small"),
            },
        )

    if st.button("⬅️ 返回", use_container_width=True, key="back_hist_final"):
        st.session_state.step = "select_vendor"
        st.rerun()



# ============================================================
# [E5] Export
# 這一區放：今日進貨明細 / LINE 匯出
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
# [E6] Analysis
# 這一區放：進銷存分析頁
# 規則：
# 1. 全部廠商：只看金額
# 2. 單一廠商：只看 庫存合計 / 這次庫存 / 期間消耗 / 日平均
# 3. 各自提供 CSV 匯出
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
    purchase_summary_df = _build_purchase_summary_df(
        store_id=st.session_state.store_id,
        start_date=start,
        end_date=end,
    )

    if not purchase_summary_df.empty and "廠商" not in purchase_summary_df.columns:
        purchase_summary_df["廠商"] = "-"

    if hist_df.empty and purchase_summary_df.empty:
        st.warning(f"⚠️ 在 {start} 到 {end} 之間查無紀錄。")
        if st.button("⬅️ 返回選單", use_container_width=True, key="back_from_analysis_no_data"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    st.markdown("---")

    # ============================================================
    # 廠商篩選
    # ============================================================
    hist_filt = hist_df.copy()
    purchase_filt = purchase_summary_df.copy()

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

    st.markdown("---")

    # ============================================================
    # 全部廠商：只看金額
    # ============================================================
    if selected_vendor == "全部廠商":
        st.subheader("📋 全部廠商金額統計")

        if purchase_filt.empty or "廠商" not in purchase_filt.columns or "採購金額" not in purchase_filt.columns:
            st.info("目前沒有可顯示的金額資料")
        else:
            vendor_summary = (
                purchase_filt.groupby("廠商", as_index=False)["採購金額"]
                .sum()
                .sort_values("採購金額", ascending=False)
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

            st.dataframe(
                vendor_summary,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "廠商": st.column_config.TextColumn(width="medium"),
                    "採購金額": st.column_config.NumberColumn("金額", format="%.1f", width="small"),
                },
            )

        if st.button("⬅️ 返回選單", use_container_width=True, key="back_from_analysis_all"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    # ============================================================
    # 單一廠商：只看 品項明細
    # ============================================================
    st.subheader(f"📦 {selected_vendor} 品項明細")

    if hist_filt.empty:
        st.info("此廠商在目前條件下無資料")
    else:
        detail_df = hist_filt.copy()

        # 隱藏完全沒變化的列
        detail_df = detail_df[
            (detail_df["庫存合計"] != 0)
            | (detail_df["這次庫存"] != 0)
            | (detail_df["期間消耗"] != 0)
            | (detail_df["日平均"] != 0)
        ].copy()

        if detail_df.empty:
            st.caption("此廠商在目前條件下無品項資料")
        else:
            show_cols = [
                "品項",
                "庫存合計",
                "這次庫存",
                "期間消耗",
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

            st.dataframe(
                export_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "品項": st.column_config.TextColumn(width="medium"),
                    "庫存合計": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "這次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "期間消耗": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "日平均": st.column_config.NumberColumn(format="%.1f", width="small"),
                },
            )

    if st.button("⬅️ 返回選單", use_container_width=True, key="back_from_analysis_single"):
        st.session_state.step = "select_vendor"
        st.rerun()


# ============================================================
# [E7] Cost Debug
# 這一區放：成本檢查頁
# ============================================================
def page_cost_debug():
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
    st.write(f"**item_id：** {selected_item_id}")
    st.write(f"**base_unit：** {base_unit or '未設定'}")
    st.write(f"**default_stock_unit：** {default_stock_unit or '未設定'}")
    st.write(f"**default_order_unit：** {default_order_unit or '未設定'}")
    st.write(f"**價格：** {unit_price}")
    st.write(f"**價格單位：** {price_unit or '未設定'}")
    st.write(f"**價格生效日：** {effective_date or '未設定'}")
    st.write(f"**base_unit_cost：** {base_unit_cost if base_unit_cost is not None else '無法計算'}")

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
# ============================================================
# [E8] Purchase Settings
# 這一區放：採購設定頁
# ============================================================
def page_purchase_settings():
    st.title("🛒 採購設定")
    st.info("此功能入口已建立，功能尚未接上。")
    st.write("目前先保留為入口頁，下一步再接廠商 / 品項管理。")
