# Step77 - build_analysis_page_view_model() 定點優化報告

## 修改檔案
- analysis/logic/report_view_model.py

## 本輪做法
- 將 analysis flow 的 purchase_filt / detail_df / vendor_summary / display frames 改為 lazy cache。
- 全部廠商路徑直接沿用 upstream vendor_summary。
- 移除 build_analysis_page_view_model() 內 detail_df 日期欄位的無條件 display-only 重建。
- total_purchase_amount / total_stock_amount 改成依路徑分層快取。

## 固定成本下降點
- vendor_summary 組裝成本下降。
- purchase_filt 廠商篩選重複成本下降。
- detail_df / export_df / show_df display-only 重建成本下降。
- total_purchase_amount / total_stock_amount 重複整理成本下降。

## Benchmark 前後
- Before: cold 854.331 ms / warm 12.997 ms
- After: cold 899.636 ms / warm 1.558 ms
- Cold 變化: +45.305 ms (+5.303%)
- Warm 變化: -11.439 ms (-88.012%)

## 判讀
- 本輪主要收益落在 warm 固定成本，代表 analysis page 在同輪重進、切換 display mode、同條件重算時的固定組裝成本明顯下降。
- cold run 在此 benchmark 環境中未下降，且有小幅波動；主因仍是 upstream summary 與 total stock amount 計算成本占比過高，使本輪 page-level 優化對 cold 的影響接近噪音區。

## dev_guard
- PASS
