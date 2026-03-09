from __future__ import annotations

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
)

# Plotly (optional)
try:
    import plotly.express as px
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False


# ============================================================
# [E4] View History
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
        key="hist_start_date"
    )
    h_end = c_h_date2.date_input(
        "結束日期",
        value=date.today(),
        key="hist_end_date"
    )

    hist_df = _build_inventory_history_summary_df(
        store_id=st.session_state.store_id,
        start_date=h_start,
        end_date=h_end,
    )

    t1, t2 = st.tabs(["📋 明細", "📈 趨勢"])

    with t1:
        if hist_df.empty:
            st.info("💡 此區間內無紀錄。")
        else:
            item_values = _clean_option_list(hist_df["品項"].dropna().tolist())
            all_i = ["全部品項"] + item_values
            sel_i = st.selectbox("🏷️ 選擇品項", options=all_i, index=0, key="hist_item_filter")

            filt_df = hist_df.copy()
            if sel_i != "全部品項":
                filt_df = filt_df[filt_df["品項"] == sel_i].copy()

            show_cols = [
                "日期顯示",
                "品項",
                "上次庫存",
                "期間進貨",
                "庫存合計",
                "這次庫存",
                "期間消耗",
                "日平均",
            ]

            render_report_dataframe(
                filt_df[show_cols],
                column_config={
                    "日期顯示": st.column_config.TextColumn("日期", width="small"),
                    "品項": st.column_config.TextColumn(width="medium"),
                    "上次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "期間進貨": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "庫存合計": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "這次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "期間消耗": st.column_config.NumberColumn(format="%.1f", width="small"),
                    "日平均": st.column_config.NumberColumn(format="%.1f", width="small"),
                }
            )

    with t2:
        if not HAS_PLOTLY:
            st.info("💡 Plotly 未安裝，無法顯示趨勢圖。")
        else:
            if hist_df.empty:
                st.info("💡 此區間內無趨勢資料。")
            else:
                item_values2 = _clean_option_list(hist_df["品項"].dropna().tolist())
                if not item_values2:
                    st.info("💡 此區間內無品項資料。")
                else:
                    sel_i2 = st.selectbox("🏷️ 選擇品項", options=item_values2, key="hist_trend_item")
                    p_df = hist_df[hist_df["品項"] == sel_i2].copy()

                    trend = (
                        p_df.groupby("日期_dt", as_index=False)["期間消耗"]
                        .sum()
                        .sort_values("日期_dt")
                    )
                    trend["日期標記"] = trend["日期_dt"].dt.strftime("%Y-%m-%d")

                    if not trend.empty:
                        fig = px.line(
                            trend,
                            x="日期標記",
                            y="期間消耗",
                            markers=True,
                            title=f"📈 【{sel_i2}】消耗趨勢",
                        )
                        fig.update_layout(
                            xaxis_type="category",
                            hovermode="x unified",
                            xaxis_title="日期",
                            yaxis_title="期間消耗",
                            dragmode=False,
                        )
                        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    if st.button("⬅️ 返回", use_container_width=True, key="back_hist_final"):
        st.session_state.step = "select_vendor"
        st.rerun()


# ============================================================
# [E5] Export
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

    from oms_core import send_line_message

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
# ============================================================
def page_analysis():
    st.title("📊 進銷存分析")

    c_date1, c_date2 = st.columns(2)
    start = c_date1.date_input("起始日期", value=date.today() - timedelta(days=14), key="ana_start")
    end = c_date2.date_input("結束日期", value=date.today(), key="ana_end")

    hist_df = _build_inventory_history_summary_df(
        store_id=st.session_state.store_id,
        start_date=start,
        end_date=end,
    )
    purchase_summary_df = _build_purchase_summary_df(
        store_id=st.session_state.store_id,
        start_date=start,
        end_date=end,
    )

    stock_df = read_table("stocktake_lines")
    stock_header_df = read_table("stocktakes")
    prices_df = read_table("prices")
    items_df = read_table("items")
    conversions_df = _get_active_df(read_table("unit_conversions"))

    if hist_df.empty and purchase_summary_df.empty:
        st.warning(f"⚠️ 在 {start} 到 {end} 之間查無紀錄。")
        if st.button("⬅️ 返回選單", use_container_width=True, key="back_from_analysis_no_data"):
            st.session_state.step = "select_vendor"
            st.rerun()
        return

    st.markdown("---")

    all_items = ["全部品項"] + _clean_option_list(hist_df.get("品項", []).dropna().tolist() if not hist_df.empty else [])
    selected_item = st.selectbox("🏷️ 選擇品項", options=all_items, index=0, key="ana_item_filter")

    hist_filt = hist_df.copy()
    purchase_filt = purchase_summary_df.copy()

    if selected_item != "全部品項":
        if not hist_filt.empty:
            hist_filt = hist_filt[hist_filt["品項"] == selected_item].copy()
        if not purchase_filt.empty:
            purchase_filt = purchase_filt[purchase_filt["品項名稱"] == selected_item].copy()

    total_buy = float(purchase_filt.get("採購金額", []).sum()) if not purchase_filt.empty else 0.0

    total_stock_value = 0.0
    
    
    if not hist_filt.empty and not items_df.empty and not prices_df.empty:
        latest_rows = hist_filt.sort_values("日期_dt").groupby("item_id", as_index=False).tail(1).copy()
        
        latest_rows["base_unit_cost"] = latest_rows.apply(
            lambda r: get_base_unit_cost(
                item_id=_norm(r.get("item_id", "")),
                target_date=end,
                items_df=items_df,
                prices_df=prices_df,
                conversions_df=conversions_df,
            ) or 0.0,
            axis=1,
        )
        latest_rows["stock_value"] = latest_rows["這次庫存"].astype(float) * latest_rows["base_unit_cost"].astype(float)
        total_stock_value = float(latest_rows["stock_value"].sum())

    st.markdown(
        f"""
        <div style='display: flex; gap: 10px; margin-bottom: 20px;'>
            <div style='flex: 1; padding: 10px; border-radius: 8px; border-left: 4px solid #50C878; background: rgba(80, 200, 120, 0.05);'>
                <div style='font-size: 11px; font-weight: 700; opacity: 0.8;'>📦 庫存殘值估計</div>
                <div style='font-size: 18px; font-weight: 800; color: #50C878;'>${total_stock_value:,.1f}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    t_detail, t_trend = st.tabs(["📋 明細", "📈 趨勢"])

        with t_detail:
            st.write("<b>📋 進銷存匯總明細</b>", unsafe_allow_html=True)
    
            if hist_filt.empty:
                st.info("💡 尚未產生進銷存資料")
            else:
                detail_df = hist_filt.copy()
    
                # 完全沒變化的列不顯示
                detail_df = detail_df[
                    (detail_df["上次庫存"] != 0)
                    | (detail_df["期間進貨"] != 0)
                    | (detail_df["期間消耗"] != 0)
                    | (detail_df["這次庫存"] != 0)
                ].copy()
    
                show_cols = [
                    "日期顯示",
                    "品項",
                    "上次庫存",
                    "期間進貨",
                    "庫存合計",
                    "這次庫存",
                    "期間消耗",
                    "日平均",
                ]
    
                st.dataframe(
                    detail_df[show_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "日期顯示": st.column_config.TextColumn("日期", width="small"),
                        "品項": st.column_config.TextColumn(width="small"),
                        "上次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                        "期間進貨": st.column_config.NumberColumn(format="%.1f", width="small"),
                        "庫存合計": st.column_config.NumberColumn(format="%.1f", width="small"),
                        "這次庫存": st.column_config.NumberColumn(format="%.1f", width="small"),
                        "期間消耗": st.column_config.NumberColumn(format="%.1f", width="small"),
                        "日平均": st.column_config.NumberColumn(format="%.1f", width="small"),
                    },
                )

    with t_trend:
        if not HAS_PLOTLY:
            st.info("💡 Plotly 未安裝，無法顯示趨勢圖。")
        else:
            if hist_filt.empty:
                st.info("💡 此條件下尚無趨勢資料。")
            else:
                trend_daily = (
                    hist_filt.groupby("日期_dt", as_index=False)["期間消耗"]
                    .sum()
                    .sort_values("日期_dt")
                )
                trend_daily["日期標記"] = trend_daily["日期_dt"].dt.strftime("%Y-%m-%d")

                if not trend_daily.empty:
                    fig1 = px.line(
                        trend_daily,
                        x="日期標記",
                        y="期間消耗",
                        markers=True,
                        title="📈 期間消耗趨勢",
                    )
                    fig1.update_layout(
                        xaxis_type="category",
                        hovermode="x unified",
                        xaxis_title="日期",
                        yaxis_title="期間消耗",
                        dragmode=False,
                    )
                    st.plotly_chart(fig1, use_container_width=True, config=PLOTLY_CONFIG)

                rank_df = (
                    hist_filt.groupby("品項", as_index=False)["期間消耗"]
                    .sum()
                    .sort_values("期間消耗", ascending=False)
                    .head(20)
                )

                if not rank_df.empty:
                    fig2 = px.bar(
                        rank_df,
                        x="品項",
                        y="期間消耗",
                        title="📊 品項期間消耗排行 (Top 20)",
                    )
                    fig2.update_layout(
                        xaxis_title="品項名稱",
                        yaxis_title="期間消耗",
                        dragmode=False,
                    )
                    st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)

    if st.button("⬅️ 返回選單", use_container_width=True, key="back_from_analysis"):
        st.session_state.step = "select_vendor"
        st.rerun()


# ============================================================
# [E7] Cost Debug
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
        axis=1
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

    item_row = work[work["item_id"].astype(str).str.strip() == str(selected_item_id).strip()].iloc[0]

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
                price_rows["is_active"].apply(lambda x: str(x).strip() in ["1", "True", "true", "YES", "yes", "是"])
            ].copy()

        if "effective_date" in price_rows.columns:
            price_rows["__eff"] = price_rows["effective_date"].apply(lambda x: x if isinstance(x, date) else None)
            price_rows["__eff"] = price_rows["effective_date"].apply(lambda x: None if str(x).strip() == "" else __import__("pandas").to_datetime(x).date())
        else:
            price_rows["__eff"] = None

        if "end_date" in price_rows.columns:
            price_rows["__end"] = price_rows["end_date"].apply(lambda x: None if str(x).strip() == "" else __import__("pandas").to_datetime(x).date())
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
        show_cols = [c for c in ["conversion_id", "from_unit", "to_unit", "ratio", "is_active"] if c in conv_show.columns]
        st.dataframe(conv_show[show_cols], use_container_width=True, hide_index=True)

    if st.button("⬅️ 返回選單", use_container_width=True, key="back_from_cost_debug"):
        st.session_state.step = "select_vendor"
        st.rerun()







