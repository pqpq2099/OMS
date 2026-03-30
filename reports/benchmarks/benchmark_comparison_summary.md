# OMS Benchmark Comparison Summary

## 基準說明

- 舊基準：zip 內原有 benchmark_results_previous.json
- 新基準：本次以最新專案版本重跑 benchmark_results.json
- 測試資料：/mnt/data/ORIVIA_OMS_DB.xlsx

## 重點對照（共同項目）

| 項目 | 舊 Cold | 新 Cold | Δ Cold ms | 舊 Warm | 新 Warm | Δ Warm ms |
|---|---:|---:|---:|---:|---:|---:|
| build_history_page_view_model() | 835.435 | 841.78 | +6.345 | 12.834 | 1.582 | -11.252 |
| _build_inventory_history_summary_df(STORE_002, 2026-03-15~2026-03-24) | 756.493 | 813.145 | +56.652 | 0.246 | 0.18 | -0.066 |
| build_stock_order_compare_view_model() | 1097.509 | 535.323 | -562.186 | 223.396 | 0.512 | -222.884 |
| _build_latest_item_metrics_df(STORE_002, 2026-03-19) | 804.934 | 485.19 | -319.744 | 0.236 | 0.176 | -0.06 |
| _build_stock_detail_df() | 350.999 | 246.226 | -104.773 | 0.349 | 0.259 | -0.09 |
| _build_purchase_detail_df() | 265.191 | 187.469 | -77.722 | 0.214 | 0.16 | -0.054 |
| load_report_shared_tables() | 173.118 | 120.143 | -52.975 | 0.249 | 0.167 | -0.082 |
| read_table(items) | 49.927 | 35.504 | -14.423 | 1.192 | 1.678 | +0.486 |
| read_table(items, force_refresh=True) | 51.028 | 31.302 | -19.726 | 47.63 | 30.33 | -17.3 |
| bust_cache(items) + read_table(items) | 43.015 | 30.329 | -12.686 | 44.672 | 36.7 | -7.972 |
| get_header(items) | 30.171 | 21.433 | -8.738 | 0.011 | 0.009 | -0.002 |

## 新基準Cold 熱點排序

1. build_history_page_view_model() — cold 841.78 ms
2. build_analysis_page_view_model() — cold 820.896 ms
3. _build_inventory_history_summary_df(STORE_002, 2026-03-15~2026-03-24) — cold 813.145 ms
4. build_stock_order_compare_view_model() — cold 535.323 ms
5. _build_latest_item_metrics_df(STORE_002, 2026-03-19) — cold 485.19 ms
6. _build_stock_detail_df() — cold 246.226 ms
7. _build_purchase_detail_df() — cold 187.469 ms
8. report_stock_source_reads() — cold 184.337 ms
9. report_purchase_source_reads() — cold 128.099 ms
10. load_report_shared_tables() — cold 120.143 ms
11. read_table(items) — cold 35.504 ms
12. read_table(items, force_refresh=True) — cold 31.302 ms
13. bust_cache(items) + read_table(items) — cold 30.329 ms
14. get_header(items) — cold 21.433 ms

## 新基準Warm 熱點排序

1. bust_cache(items) + read_table(items) — warm 36.7 ms
2. read_table(items, force_refresh=True) — warm 30.33 ms
3. read_table(items) — warm 1.678 ms
4. report_stock_source_reads() — warm 1.66 ms
5. build_analysis_page_view_model() — warm 1.654 ms
6. build_history_page_view_model() — warm 1.582 ms
7. report_purchase_source_reads() — warm 1.261 ms
8. build_stock_order_compare_view_model() — warm 0.512 ms
9. _build_stock_detail_df() — warm 0.259 ms
10. _build_inventory_history_summary_df(STORE_002, 2026-03-15~2026-03-24) — warm 0.18 ms
11. _build_latest_item_metrics_df(STORE_002, 2026-03-19) — warm 0.176 ms
12. load_report_shared_tables() — warm 0.167 ms
13. _build_purchase_detail_df() — warm 0.16 ms
14. get_header(items) — warm 0.009 ms

## 判讀

- build_history_page_view_model()：cold 841.78 ms / warm 1.582 ms / speedup 532.1x
- build_stock_order_compare_view_model()：cold 535.323 ms / warm 0.512 ms / speedup 1045.55x
- build_analysis_page_view_model()：cold 820.896 ms / warm 1.654 ms / speedup 496.31x
- load_report_shared_tables()：cold 120.143 ms / warm 0.167 ms / speedup 719.42x

## 結論

- warm run 已明顯收斂，主要互動畫面固定成本幾乎都壓到 2 ms 內。
- 目前剩餘問題主要集中在 cold run 首次建構成本，而不是使用中切頁或重複操作成本。
- 因此下一步較建議先做壓測封版；除非你要再追一次首次開頁體感，才有理由再做最後一個 cold-only 定點優化。