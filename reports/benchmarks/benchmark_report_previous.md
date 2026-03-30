# OMS Performance Benchmark Report

- Workbook: `/mnt/data/oms_work/OMS/ORIVIA_OMS_DB.xlsx`
- Cold repeat: 2
- Warm repeat: 3
- Store scope: `STORE_002`
- History window: `2026-03-15` ~ `2026-03-24`
- Compare date: `2026-03-19`

## 結果摘要

| 類別 | 項目 | Cold mean (ms) | Warm mean (ms) | 加速比 | 輸出摘要 |
|---|---:|---:|---:|---:|---|
| spreadsheet_backend | read_table(items) | 49.927 | 1.192 | 41.89x | `{"rows": 146, "cols": 29}` |
| spreadsheet_backend | get_header(items) | 30.171 | 0.011 | 2742.82x | `{"size": 29, "sample": ["item_id", "brand_id", "default_vendor_id", "item_name", "item_name_zh"]}` |
| spreadsheet_backend | read_table(items, force_refresh=True) | 51.028 | 47.63 | 1.07x | `{"rows": 146, "cols": 29}` |
| spreadsheet_backend | bust_cache(items) + read_table(items) | 43.015 | 44.672 | 0.96x | `{"rows": 146, "cols": 29}` |
| report_calculations | _build_inventory_history_summary_df(STORE_002, 2026-03-15~2026-03-24) | 756.493 | 0.246 | 3075.17x | `{"rows": 396, "cols": 22}` |
| report_calculations | _build_stock_detail_df() | 350.999 | 0.349 | 1005.73x | `{"rows": 396, "cols": 53}` |
| report_calculations | _build_purchase_detail_df() | 265.191 | 0.214 | 1239.21x | `{"rows": 144, "cols": 59}` |
| report_calculations | _build_latest_item_metrics_df(STORE_002, 2026-03-19) | 804.934 | 0.236 | 3410.74x | `{"rows": 139, "cols": 22}` |
| analysis_flow | load_report_shared_tables() | 173.118 | 0.249 | 695.25x | `{"items": {"rows": 146, "cols": 29}, "vendors": {"rows": 13, "cols": 31}, "stores": {"rows": 5, "cols": 26}, "prices": {"rows": 146, "cols": 26}, "unit_conversions": {"rows": 18, "cols": 26}}` |
| analysis_flow | build_history_page_view_model() | 835.435 | 12.834 | 65.1x | `{"hist_df": {"rows": 396, "cols": 22}, "vendor_options": {"size": 11, "sample": ["全部廠商", "JENNY", "元和", "國豐", "太古"]}, "item_options": {"size": 1, "sample": ["全部品項"]}, "detail_df": {"rows": 273, "cols": 22}, "export_df": {"rows": 0, "cols": 0}, "show_df": {"rows": 0, "cols": 0}}` |
| analysis_flow | build_stock_order_compare_view_model() | 1097.509 | 223.396 | 4.91x | `{"preview": {"rows": 65, "cols": 4}, "vendor_options": {"size": 6, "sample": ["全部廠商", "JENNY", "元和", "國豐", "昶翔"]}, "has_source": true}` |

## Cold run 熱點排序

1. build_stock_order_compare_view_model() — cold 1097.509 ms / warm 223.396 ms / 加速比 4.91x
2. build_history_page_view_model() — cold 835.435 ms / warm 12.834 ms / 加速比 65.1x
3. _build_latest_item_metrics_df(STORE_002, 2026-03-19) — cold 804.934 ms / warm 0.236 ms / 加速比 3410.74x
4. _build_inventory_history_summary_df(STORE_002, 2026-03-15~2026-03-24) — cold 756.493 ms / warm 0.246 ms / 加速比 3075.17x
5. _build_stock_detail_df() — cold 350.999 ms / warm 0.349 ms / 加速比 1005.73x
6. _build_purchase_detail_df() — cold 265.191 ms / warm 0.214 ms / 加速比 1239.21x
7. load_report_shared_tables() — cold 173.118 ms / warm 0.249 ms / 加速比 695.25x
8. read_table(items, force_refresh=True) — cold 51.028 ms / warm 47.63 ms / 加速比 1.07x
9. read_table(items) — cold 49.927 ms / warm 1.192 ms / 加速比 41.89x
10. bust_cache(items) + read_table(items) — cold 43.015 ms / warm 44.672 ms / 加速比 0.96x
11. get_header(items) — cold 30.171 ms / warm 0.011 ms / 加速比 2742.82x

## 下一輪瓶頸判讀

- build_stock_order_compare_view_model()：cold 1097.509 ms、warm 223.396 ms、加速比 4.91x。頁面 view model 雖有共享快取，但組裝、merge、格式化仍有固定成本。
- build_history_page_view_model()：cold 835.435 ms、warm 12.834 ms、加速比 65.1x。頁面 view model 雖有共享快取，但組裝、merge、格式化仍有固定成本。
- _build_latest_item_metrics_df(STORE_002, 2026-03-19)：cold 804.934 ms、warm 0.236 ms、加速比 3410.74x。報表衍生 DataFrame 建構仍是主要 CPU 成本。
- _build_inventory_history_summary_df(STORE_002, 2026-03-15~2026-03-24)：cold 756.493 ms、warm 0.246 ms、加速比 3075.17x。報表衍生 DataFrame 建構仍是主要 CPU 成本。
- _build_stock_detail_df()：cold 350.999 ms、warm 0.349 ms、加速比 1005.73x。報表衍生 DataFrame 建構仍是主要 CPU 成本。

## 建議優化順序

1. 先看 cold run 最慢的 report_calculations 流程，優先檢查大型 merge / apply / repeated copy。
2. 再看 spreadsheet_backend 的 force_refresh / bust_cache 後重讀，確認是否有不必要整表重抓。
3. 最後看 analysis view model 組裝層，尤其是 vendor/item 補欄、格式化與 display-only merge。
