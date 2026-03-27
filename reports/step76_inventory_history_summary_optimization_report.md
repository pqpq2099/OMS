# Step76 `_build_inventory_history_summary_df()` 定點優化報告

## 修改檔案清單

- `shared/services/report_calculations.py`

- `reports/benchmarks/benchmark_results.json`

- `reports/benchmarks/benchmark_report.md`

- `dev_guard/latest_guard_report.json`

- `dev_guard/latest_guard_report.md`

## 本輪收斂內容

- 將 summary builder 的逐列組裝改成「先欄位化、後整體輸出」，保留原輸出欄位與排序。
- 以 `__effective_vendor_id` 統一 stock / purchase 對齊鍵，避免每列重複 fallback vendor 判斷。
- 將 purchase display qty 轉換改為 `_compute_display_qty_series()` 批次處理，移除逐列 `convert_unit` 包裝迴圈。
- 將 same-day order 改為一次 merge，移除 `(item_id, vendor_id, date)` 字典逐列查找。
- 將區間進貨改為每個 item/vendor group 一次 `np.searchsorted` 批次定位累積值，移除逐列 DataFrame `searchsorted + iloc`。
- 將消耗、天數、日平均改為欄位運算，只保留日平均 rounding 的 Python `round()` 相容行為。

## 哪些 summary builder 成本被降低

- 重複 sort / dedupe 後的 per-row lookup 成本下降。
- purchase interval lookup 從「每列抓 group DataFrame」改成「每 group 一次 numpy array 查找」。
- 同日叫貨與區間進貨不再各自用 dict + row loop 重做。
- display unit fallback map 改為一次建立，之後用 series map 套用。

## Benchmark 前後差異

| 項目 | Before cold ms | After cold ms | Δ cold ms | Before warm ms | After warm ms | Δ warm ms |
|---|---:|---:|---:|---:|---:|---:|
| _build_inventory_history_summary_df(STORE_002, 2026-03-15~2026-03-24) | 756.493 | 425.924 | -330.569 | 0.246 | 0.105 | -0.141 |
| build_history_page_view_model() | 835.435 | 465.869 | -369.566 | 12.834 | 0.821 | -12.013 |

## Dev Guard 結果

- `guard_result`: PASS
- `compileall`: PASS
- `import_smoke`: PASS
- `router_smoke`: PASS
- `page_exports`: PASS
- `page_boundary`: PASS