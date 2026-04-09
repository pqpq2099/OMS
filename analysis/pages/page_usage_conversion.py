"""使用量換算頁面。

上傳外送平台銷售報表 → 左欄顯示銷售明細 → 右欄顯示換算結果。
"""
from __future__ import annotations

import streamlit as st

from analysis.logic.logic_usage_conversion import process_report


def page_usage_conversion():
    st.title("📋 使用量換算")

    uploaded = st.file_uploader(
        "上傳外送平台銷售報表",
        type=["xlsx"],
        key="usage_upload",
        label_visibility="collapsed",
    )

    if not uploaded:
        st.caption("請上傳 report_UberEats_YYYYMMDD_YYYYMMDD.xlsx 或 report_foodpanda_YYYYMMDD_YYYYMMDD.xlsx")
        return

    result = process_report(uploaded)

    if result.get("error"):
        st.error(result["error"])
        return

    st.info(f"平台：{result['platform']}　｜　區間：{result['date_range']}")

    col_left, col_right = st.columns([1.2, 1], gap="large")

    with col_left:
        sales = result["sales_df"]
        st.subheader(f"銷售品項（{len(sales)} 項）")
        st.dataframe(
            sales.rename(columns={"item_name": "品項名稱", "qty": "銷售數量"}),
            use_container_width=True,
            hide_index=True,
            height=500,
        )

        unmatched = result.get("unmatched", [])
        if unmatched:
            st.warning(f"⚠ 尚未有轉換資料（{len(unmatched)} 項）")
            for name in unmatched:
                st.caption(f"　· {name}")

    with col_right:
        rdf = result.get("result_df")
        if rdf is None or rdf.empty:
            st.subheader("換算結果")
            st.info("無可換算的品項")
            return

        st.subheader(f"換算結果（{len(rdf)} 項）")
        display = rdf[["item_name", "display_qty", "display_unit"]].copy()
        display.columns = ["品項名稱", "數量", "單位"]
        st.dataframe(display, use_container_width=True, hide_index=True, height=500)
