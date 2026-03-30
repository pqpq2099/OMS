# OMS System Rules

## 0. 執行模式（最高優先）
所有任務必須遵循：
1. 先分析，不可直接修改
2. 必須提出最小修改方案
3. 必須列出修改步驟（檔案 + 位置）
4. 未確認前不可動手修改
5. 修改後必須通過 dev_guard

違反以上任一條，視為任務失敗。

## 1. 輸出模式（固定）
所有任務輸出必須分成兩段，不可混寫：

### A. 分析版（給人看）
用途：給使用者 / GPT 查看
內容可包含：
- 影響檔案
- legacy 流程
- 資料流
- 風險點
- 最小修改路徑

### B. 執行版（給 Claude Code 做）
用途：直接執行
必須精簡，不可帶原因、背景、解釋。
只能保留：
- 任務名稱
- 原則
- Step 1 / Step 2 / Step 3
- 檔案
- 修改
- 保留
- 結果
- 驗證
- 禁止事項
- 輸出檔案規則

## 2. 執行版固定格式
執行版一律使用以下格式：

【任務名稱】

【原則】
- 最小修改
- 保留舊接口
- 不可跨模組修改
- 不可整檔重寫

【Step 1】
檔案：
修改：
保留：
結果：

【Step 2】
檔案：
修改：
保留：
結果：

【Step 3】
檔案：
修改：
保留：
結果：

【驗證】
- 開哪個頁面
- 操作什麼
- 預期結果

【禁止事項】
- 不可刪舊接口
- 不可整檔重寫
- 不可變更未指定範圍

【輸出檔案規則】
- 所有輸出需同時顯示在對話與實際建立檔案
- 輸出路徑：F:\\Google Backup\\Claude Code\\out
- 檔名格式：YYYYMMDD_HHMM + 用途

## Architecture
- pages: UI only
- logic: process / decision
- services: data / rules
- shared: reusable modules

## Development Rules
- minimal change only
- never rewrite whole file
- keep legacy interfaces
- single solution only
- step-by-step modification

## UI Rules
- no UI change
- no new features

## Data Rules
- all item list sorted by item_id
- operation_date = main date
- order detail = delivery_date

## Safety Rules
- do not guess requirements
- do not refactor unless asked
- do not modify unrelated files
