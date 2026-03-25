# OMS AI 開發控制模板

## 任務定位

你現在處理的是一個已完成架構凍結與 validation baseline 全綠的 OMS 專案。

本次任務只允許在指定範圍內修改，先完成指令，再回報，不順手優化其他模組。

## 固定禁止事項

- 禁止在 page 層撰寫業務邏輯。
- 禁止 page 直接呼叫 write / service / 外部 IO。
- 禁止 page 直接呼叫 create_ / update_ / reset_ / send_。
- 禁止在 page 層新增 DataFrame merge / groupby / map / drop_duplicates 等重整理。
- 禁止修改 route key。
- 禁止新增 fallback route、alias route、臨時相容層。
- 禁止改 UI。
- 禁止改業務流程。
- 禁止重構。
- 禁止搬檔。
- 禁止未經指示順手優化。

## 允許方向

- page 只能保留 UI、session、按鈕觸發、logic 呼叫、結果顯示。
- logic 負責流程判斷、驗證、顯示模型、提交前整理。
- services / runtime 負責寫入與外部行為。
- 若 page 發現越層，只能改成 page -> logic wrapper -> service/runtime。

## 修改後固定驗證

修改完成後，必須執行：

```bash
python dev_guard/run_local_guard.py
```

## 固定輸出格式

1. 修改檔案清單
2. 修正前後差異說明
3. 驗證結果摘要
4. 是否仍有違規

## 驗證未過處理規則

- 只回報本次修改範圍內發現的阻塞點。
- 不擴大修改範圍。
- 不以重構取代修正。
- 驗證未過不得宣稱完成。
