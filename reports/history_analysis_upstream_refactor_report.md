# history / analysis 上游共享結果拆解報告

## 修改檔案清單
- analysis/logic/report_view_model.py

## 本次共享化的 upstream result
- history summary + vendor enrich：統一由 `_build_history_vendor_enriched_df()` 組裝，`build_history_with_vendor()` / `build_analysis_with_vendor()` 只保留轉接。
- purchase filter upstream：抽成 `_build_purchase_filtered_df()`，統一處理 store/date 篩選、`日期`、`廠商`、`進貨金額` 補欄。
- vendor / item filter option upstream：抽成 `_build_vendor_item_option_maps()` 與共享 `vendor_options`。
- history / analysis 共用 upstream cache：新增 `_build_history_analysis_shared_upstream()`，一次組裝並快取：
  - `hist_df`
  - `purchase_filt`
  - `vendor_options`
  - `vendor_item_option_map`
  - `base_detail_df`
  - `vendor_summary`
- detail display 前整理：
  - 非零明細列過濾抽成 `_build_nonzero_detail_df()`
  - detail export/show frame 抽成 `_build_report_detail_frames()`
  - vendor summary 抽成 `_build_vendor_summary_df()`

## 被移除的重複組裝
- history / analysis 各自重做的 vendor enrich merge。
- analysis page 內部重做的 purchase detail 篩選與顯示欄位補齊。
- history page 內部重做的 item option vendor 對應整理。
- history / analysis 各自重做的 detail 非零列篩選。
- history / analysis 各自重做的 export_df / show_df 顯示前組裝流程。

## benchmark 前後差異（ms）
測試條件：STORE_002 / 2026-03-15~2026-03-24。

| Case | Before cold | After cold | Δ cold | Before warm | After warm | Δ warm |
|---|---:|---:|---:|---:|---:|---:|
| history | 526.184 | 575.675 | +49.491 | 6.799 | 1.295 | -5.504 |
| analysis | 542.726 | 543.426 | +0.700 | 24.224 | 11.686 | -12.538 |
| history_then_analysis | 526.240 | 525.114 | -1.126 | 30.142 | 13.787 | -16.355 |
| analysis_then_history | 542.467 | 524.197 | -18.270 | 31.944 | 13.332 | -18.612 |

### 解讀
- 單獨 cold run 並沒有明顯下降，因為本次主軸不是重寫 summary builder，而是把兩個 page view model 之間可共用的 upstream 組裝抽成一次。
- 真正改善點出現在 warm 與同輪連續切換 history / analysis：第二個 page view model 直接重用 upstream cache，不再重做相同整理。
- `history_then_analysis` / `analysis_then_history` warm 成本從約 30~32 ms 降到約 13~14 ms，符合本次任務目標。

## 顯示結果驗證
- 以 history / analysis 的 full / mobile、全部廠商 / 指定廠商案例做前後比對。
- DataFrame shape / columns / CSV 內容全部一致。
- 結果：PASS（顯示結果未改變）

## dev_guard 結果
- guard_result: PASS
- compileall: PASS
- import_smoke: PASS
- router_smoke: PASS
- page_exports: PASS
- page_boundary: PASS

## 備註
- 本次未動 compare flow。
- 未改 UI / route / 顯示欄位 / 資料格式。
- 只調整 `analysis/logic/report_view_model.py`。
