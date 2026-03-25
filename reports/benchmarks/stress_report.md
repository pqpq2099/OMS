# OMS 大資料量壓力測試報告

- Base workbook: `/mnt/data/oms_proj/OMS/ORIVIA_OMS_DB.xlsx`
- Factors: 1x, 3x, 10x, 30x
- Repeat policy: 1x/3x = cold 2 warm 3；10x = cold 2 warm 2；30x = cold 1 warm 1
- 放大量方式：只擴張 transaction 類資料表（stocktakes / stocktake_lines / purchase_orders / purchase_order_lines），主資料表不變。
- 每份複本都加上新 ID，並把日期平移到未來年度，避免改變本次 2026-03-15~2026-03-24 / 2026-03-19 視窗的結果集合。

## 放大量工作簿摘要

| 倍數 | stocktakes | stocktake_lines | purchase_orders | purchase_order_lines | workbook |
|---:|---:|---:|---:|---:|---|
| 1x | 27 | 396 | 24 | 144 | `ORIVIA_OMS_DB_1x.xlsx` |
| 3x | 81 | 1188 | 72 | 432 | `ORIVIA_OMS_DB_3x.xlsx` |
| 10x | 270 | 3960 | 240 | 1440 | `ORIVIA_OMS_DB_10x.xlsx` |
| 30x | 810 | 11880 | 720 | 4320 | `ORIVIA_OMS_DB_30x.xlsx` |

## 各流程耗時總表（Cold mean ms）

| 流程 | 1x | 3x | 10x | 30x |
|---|---:|---:|---:|---:|
| _build_stock_detail_df() | 184.547 | 272.678 | 754.613 | 2181.762 |
| _build_purchase_detail_df() | 90.533 | 150.083 | 386.193 | 949.598 |
| _build_latest_item_metrics_df(STORE_002, 2026-03-19) | 316.942 | 538.963 | 1425.085 | 3411.086 |
| _build_inventory_history_summary_df(STORE_002, 2026-03-15~2026-03-24) | 331.419 | 522.165 | 1225.463 | 3468.97 |
| build_history_page_view_model() | 342.16 | 518.303 | 1197.461 | 3578.122 |
| build_stock_order_compare_view_model() | 45.697 | 49.319 | 46.085 | 47.561 |
| build_analysis_page_view_model() | 504.066 | 705.767 | 1432.983 | 3569.692 |

## 各流程耗時總表（Warm mean ms）

| 流程 | 1x | 3x | 10x | 30x |
|---|---:|---:|---:|---:|
| _build_stock_detail_df() | 0.715 | 1.42 | 2.926 | 5.174 |
| _build_purchase_detail_df() | 0.472 | 0.707 | 1.378 | 1.73 |
| _build_latest_item_metrics_df(STORE_002, 2026-03-19) | 0.126 | 0.115 | 0.123 | 0.103 |
| _build_inventory_history_summary_df(STORE_002, 2026-03-15~2026-03-24) | 0.415 | 0.401 | 0.441 | 0.406 |
| build_history_page_view_model() | 7.051 | 8.308 | 7.776 | 7.323 |
| build_stock_order_compare_view_model() | 0.679 | 0.57 | 0.634 | 0.82 |
| build_analysis_page_view_model() | 202.443 | 163.295 | 179.122 | 200.679 |

## 擴張型態判讀（以 Cold mean 為主）

| 流程 | 型態 | 3x/1x | 10x/1x | 30x/1x | 判讀 |
|---|---|---:|---:|---:|---|
| _build_stock_detail_df() | sublinear | 1.478 | 4.089 | 11.822 | 成長低於資料倍數，代表固定成本占比仍高。 |
| _build_purchase_detail_df() | sublinear | 1.658 | 4.266 | 10.489 | 成長低於資料倍數，代表固定成本占比仍高。 |
| _build_latest_item_metrics_df(STORE_002, 2026-03-19) | sublinear | 1.701 | 4.496 | 10.762 | 成長低於資料倍數，代表固定成本占比仍高。 |
| _build_inventory_history_summary_df(STORE_002, 2026-03-15~2026-03-24) | sublinear | 1.576 | 3.698 | 10.467 | 成長低於資料倍數，代表固定成本占比仍高。 |
| build_history_page_view_model() | sublinear | 1.515 | 3.5 | 10.457 | 成長低於資料倍數，代表固定成本占比仍高。 |
| build_stock_order_compare_view_model() | sublinear | 1.079 | 1.008 | 1.041 | 成長低於資料倍數，代表固定成本占比仍高。 |
| build_analysis_page_view_model() | sublinear | 1.4 | 2.843 | 7.082 | 成長低於資料倍數，代表固定成本占比仍高。 |

## 新瓶頸排序（30x cold）

1. build_history_page_view_model() — 30x cold 3578.122 ms / 1x cold 342.16 ms / 放大量比 10.457x
2. build_analysis_page_view_model() — 30x cold 3569.692 ms / 1x cold 504.066 ms / 放大量比 7.082x
3. _build_inventory_history_summary_df(STORE_002, 2026-03-15~2026-03-24) — 30x cold 3468.97 ms / 1x cold 331.419 ms / 放大量比 10.467x
4. _build_latest_item_metrics_df(STORE_002, 2026-03-19) — 30x cold 3411.086 ms / 1x cold 316.942 ms / 放大量比 10.762x
5. _build_stock_detail_df() — 30x cold 2181.762 ms / 1x cold 184.547 ms / 放大量比 11.822x
6. _build_purchase_detail_df() — 30x cold 949.598 ms / 1x cold 90.533 ms / 放大量比 10.489x
7. build_stock_order_compare_view_model() — 30x cold 47.561 ms / 1x cold 45.697 ms / 放大量比 1.041x

## 下一輪建議優化順序

1. build_history_page_view_model()（sublinear）— history flow 同時吃 summary/detail builder，適合先拆 upstream 成本與 page 組裝成本。
2. build_analysis_page_view_model()（sublinear）— 30x warm 成本已高，代表 display-only 格式化與組裝本身就有固定成本，需要從上游共享結果切開看。
3. _build_inventory_history_summary_df(STORE_002, 2026-03-15~2026-03-24)（sublinear）— 重點檢查日期過濾前的大 working set、以及 stock/purchase detail 重用路徑。
4. _build_latest_item_metrics_df(STORE_002, 2026-03-19)（sublinear）— 優先看 pair window 後仍存在的 purchase aggregation、merge 欄位膨脹、與 item/vendor lookup 重建。
5. _build_stock_detail_df()（sublinear）— 先看 builder 內 merge 欄位裁切與重複標籤補齊。
