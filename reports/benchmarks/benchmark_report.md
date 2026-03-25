# OMS Performance Benchmark Report

- Workbook: `/mnt/data/ORIVIA_OMS_DB.xlsx`
- Cold repeat: 2
- Warm repeat: 3
- Store scope: `STORE_002`
- History window: `2026-03-15` ~ `2026-03-24`
- Compare date: `2026-03-19`

## 結果摘要

| 類別 | 項目 | Cold mean (ms) | Warm mean (ms) | 加速比 | 輸出摘要 |
|---|---:|---:|---:|---:|---|
| spreadsheet_backend | read_table(items) | 35.504 | 1.678 | 21.16x | `{"rows": 146, "cols": 29}` |
| spreadsheet_backend | get_header(items) | 21.433 | 0.009 | 2381.44x | `{"size": 29, "sample": ["item_id", "brand_id", "default_vendor_id", "item_name", "item_name_zh"]}` |
| spreadsheet_backend | read_table(items, force_refresh=True) | 31.302 | 30.33 | 1.03x | `{"rows": 146, "cols": 29}` |
| spreadsheet_backend | bust_cache(items) + read_table(items) | 30.329 | 36.7 | 0.83x | `{"rows": 146, "cols": 29}` |
| spreadsheet_backend | report_stock_source_reads() | 184.337 | 1.66 | 111.05x | `{"stocktakes": {"rows": 27, "cols": 30}, "stocktake_lines": {"rows": 396, "cols": 31}, "items": {"rows": 146, "cols": 29}, "vendors": {"rows": 13, "cols": 31}, "stores": {"rows": 5, "cols": 26}, "unit_conversions": {"rows": 18, "cols": 26}}` |
| spreadsheet_backend | report_purchase_source_reads() | 128.099 | 1.261 | 101.59x | `{"purchase_orders": {"rows": 24, "cols": 28}, "purchase_order_lines": {"rows": 144, "cols": 34}, "vendors": {"rows": 13, "cols": 31}, "items": {"rows": 146, "cols": 29}, "stores": {"rows": 5, "cols": 26}}` |
| report_calculations | _build_inventory_history_summary_df(STORE_002, 2026-03-15~2026-03-24) | 813.145 | 0.18 | 4517.47x | `{"rows": 396, "cols": 22}` |
| report_calculations | _build_stock_detail_df() | 246.226 | 0.259 | 950.68x | `{"rows": 396, "cols": 53}` |
| report_calculations | _build_purchase_detail_df() | 187.469 | 0.16 | 1171.68x | `{"rows": 144, "cols": 59}` |
| report_calculations | _build_latest_item_metrics_df(STORE_002, 2026-03-19) | 485.19 | 0.176 | 2756.76x | `{"rows": 139, "cols": 22}` |
| analysis_flow | load_report_shared_tables() | 120.143 | 0.167 | 719.42x | `{"items": {"rows": 146, "cols": 29}, "vendors": {"rows": 13, "cols": 31}, "stores": {"rows": 5, "cols": 26}, "prices": {"rows": 146, "cols": 26}, "unit_conversions": {"rows": 18, "cols": 26}}` |
| analysis_flow | build_history_page_view_model() | 841.78 | 1.582 | 532.1x | `{"hist_df": {"rows": 396, "cols": 22}, "vendor_options": {"size": 11, "sample": ["全部廠商", "JENNY", "元和", "國豐", "太古"]}, "item_options": {"size": 1, "sample": ["全部品項"]}, "detail_df": {"rows": 273, "cols": 22}, "export_df": {"rows": 0, "cols": 0}, "show_df": {"rows": 0, "cols": 0}}` |
| analysis_flow | build_stock_order_compare_view_model() | 535.323 | 0.512 | 1045.55x | `{"preview": {"rows": 65, "cols": 4}, "vendor_options": {"size": 6, "sample": ["全部廠商", "JENNY", "元和", "國豐", "昶翔"]}, "has_source": true}` |
| analysis_flow | build_analysis_page_view_model() | 820.896 | 1.654 | 496.31x | `{"hist_df": {"rows": 396, "cols": 22}, "purchase_filt": {"rows": 144, "cols": 62}, "vendor_options": {"size": 11, "sample": ["全部廠商", "JENNY", "元和", "國豐", "太古"]}, "total_purchase_amount": 206302.49999999997, "total_stock_amount": 0.0, "vendor_summary": {"rows": 24, "cols": 3}, "detail_df": {"rows": 273, "cols": 22}, "export_df": {"rows": 0, "cols": 0}, "show_df": {"rows": 0, "cols": 0}}` |

## Cold run 熱點排序

1. build_history_page_view_model() — cold 841.78 ms / warm 1.582 ms / 加速比 532.1x
2. build_analysis_page_view_model() — cold 820.896 ms / warm 1.654 ms / 加速比 496.31x
3. _build_inventory_history_summary_df(STORE_002, 2026-03-15~2026-03-24) — cold 813.145 ms / warm 0.18 ms / 加速比 4517.47x
4. build_stock_order_compare_view_model() — cold 535.323 ms / warm 0.512 ms / 加速比 1045.55x
5. _build_latest_item_metrics_df(STORE_002, 2026-03-19) — cold 485.19 ms / warm 0.176 ms / 加速比 2756.76x
6. _build_stock_detail_df() — cold 246.226 ms / warm 0.259 ms / 加速比 950.68x
7. _build_purchase_detail_df() — cold 187.469 ms / warm 0.16 ms / 加速比 1171.68x
8. report_stock_source_reads() — cold 184.337 ms / warm 1.66 ms / 加速比 111.05x
9. report_purchase_source_reads() — cold 128.099 ms / warm 1.261 ms / 加速比 101.59x
10. load_report_shared_tables() — cold 120.143 ms / warm 0.167 ms / 加速比 719.42x
11. read_table(items) — cold 35.504 ms / warm 1.678 ms / 加速比 21.16x
12. read_table(items, force_refresh=True) — cold 31.302 ms / warm 30.33 ms / 加速比 1.03x
13. bust_cache(items) + read_table(items) — cold 30.329 ms / warm 36.7 ms / 加速比 0.83x
14. get_header(items) — cold 21.433 ms / warm 0.009 ms / 加速比 2381.44x

## 下一輪瓶頸判讀

- build_history_page_view_model()：cold 841.78 ms、warm 1.582 ms、加速比 532.1x。頁面 view model 雖有共享快取，但組裝、merge、格式化仍有固定成本。
- build_analysis_page_view_model()：cold 820.896 ms、warm 1.654 ms、加速比 496.31x。頁面 view model 雖有共享快取，但組裝、merge、格式化仍有固定成本。
- _build_inventory_history_summary_df(STORE_002, 2026-03-15~2026-03-24)：cold 813.145 ms、warm 0.18 ms、加速比 4517.47x。報表衍生 DataFrame 建構仍是主要 CPU 成本。
- build_stock_order_compare_view_model()：cold 535.323 ms、warm 0.512 ms、加速比 1045.55x。頁面 view model 雖有共享快取，但組裝、merge、格式化仍有固定成本。
- _build_latest_item_metrics_df(STORE_002, 2026-03-19)：cold 485.19 ms、warm 0.176 ms、加速比 2756.76x。報表衍生 DataFrame 建構仍是主要 CPU 成本。

## 建議優化順序

1. 先看 cold run 最慢的 report_calculations 流程，優先檢查大型 merge / apply / repeated copy。
2. 再看 spreadsheet_backend 的 force_refresh / bust_cache 後重讀，確認是否有不必要整表重抓。
3. 最後看 analysis view model 組裝層，尤其是 vendor/item 補欄、格式化與 display-only merge。
