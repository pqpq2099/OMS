---
name: oms-bugfix-minimal-change
description: 當任務是修單點錯誤、避免擴散、保持既有流程穩定時，使用這個 Skill。
---

# OMS Bugfix Minimal Change

## 何時使用
遇到以下情況時使用：
- 某頁面報錯
- 某個 payload / validation / query 出錯
- 既有流程可定位到單點 bug
- 使用者明確要求不要擴大修改

## 核心原則
1. 先定位根因，不先亂修表面
2. 只修這次錯誤直接相關範圍
3. 不順手改命名、不順手優化結構
4. 如果錯誤根因是 contract 問題，改用 schema-alignment Skill
5. 保持 UI、流程、操作習慣不變

## 執行步驟
### Step 1：重現與定位
先確認：
- 錯誤發生在哪個頁面 / 哪個函式
- 實際觸發條件
- 錯誤屬於哪一類：UI、validation、payload、schema、service、route

### Step 2：縮小範圍
只列這次直接相關檔案。
通常不應超過：
- 1 個 page
- 1～2 個 logic / service
- 1 個共用層輔助檔

### Step 3：找根因
至少回答：
- 錯的是值、型別、欄位、條件判斷，還是流程順序
- 是輸入端錯，還是 service / DB 對齊錯
- 是否已有既有 helper 可沿用

### Step 4：局部修正
採以下優先順序：
1. 修條件判斷
2. 修 mapping / coercion
3. 修 validation
4. 修局部 fallback
5. 必要時修 service

### Step 5：搜尋相同錯法
用搜尋確認是否還有同類錯誤殘留，但只記錄，不擴大修改範圍。
除非它就在同一條流程上，否則不要一起改。

### Step 6：驗證
至少做：
- 重跑原錯誤路徑
- 驗證未破壞相鄰功能
- `python dev_guard/run_local_guard.py`

## 什麼情況不能用這個 Skill
以下情況不要用 minimal bugfix，改用其他 Skill：
- DB schema 與 payload 大量不一致
- 一改就牽涉多個 table / migration
- 本質是模組拆分或資料源切換
- 錯誤來自整體 contract 設計不清

## 輸出格式
### 分析版
- 錯誤位置
- 根因
- 影響檔案
- 最小修改方案
- 驗證方式

### 執行版
- 任務名稱
- 原則
- Step 1 / Step 2 / Step 3
- 修改檔案
- 驗證
- 禁止事項

## 禁止事項
- 不可把 bugfix 做成重構
- 不可順手改 UI / 文案 / 路由
- 不可因為看不順眼就整理整個模組
