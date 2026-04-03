---
name: oms-schema-alignment
description: 當 Supabase schema、table contract、payload、validation、service mapping 不一致時，使用這個 Skill 做單一路徑對齊。
---

# OMS Schema Alignment

## 何時使用
遇到以下情況時使用：
- Supabase schema 與主程式 payload 不一致
- 欄位名稱、型別、nullable、default 對不起來
- 採購設定、叫貨、庫存、歷史頁讀寫時出現 contract 類錯誤
- migration 與 code path 不一致
- require_price / unit conversion / operation_date 規則未正確落地

## 核心原則
1. 先分析，再修改
2. 先定義 target contract，再改現況
3. 優先 migration，不在多處 code 硬補 schema 差異
4. 嚴格最小修改
5. rename 風險高時，採 add → backfill → switch → verify → cleanup
6. pages 不做 schema 修補

## 必掃檔案
至少掃描：
- `supabase/migrations/*`
- `shared/services/table_contract.py`
- `shared/services/data_backend.py`
- `shared/services/supabase_client.py`
- 這次任務對應模組的 `pages / logic / services`
- 任何直接使用 table name / payload key 的檔案

## 執行步驟
### Step 1：掃描現況
列出：
- 相關 table / view / migration
- 主程式實際使用的 payload key
- 寫入 / 更新 / 查詢路徑
- validation 與 fallback
- 是否有 legacy 欄位或橋接邏輯

### Step 2：定義 target contract
輸出一份簡表，至少包含：
- table name
- column name
- type
- nullable
- default
- PK / unique / FK / check
- 程式使用端對應 key

### Step 3：做 diff
按以下分類整理：
- DB 缺欄位
- code 傳錯 key
- type 不一致
- nullable / required 不一致
- default 不一致
- unique / FK / check 缺失
- RLS / policy 風險
- legacy 欄位仍殘留

### Step 4：先改資料庫
只做必要 migration：
- add / alter / set default / set not null / add constraint
- 必要時做 backfill
- 不做危險大改名，除非已證明必要且已掃描引用

### Step 5：再改主程式
只修改與 contract 直接相關內容：
- repository / service / logic
- query / select
- insert / update payload
- validation / transform / type coercion
- fallback / default handling

### Step 6：搜尋殘留引用
全專案搜尋：
- 舊 key
- 舊欄位名
- 舊 table path
- 舊 fallback

### Step 7：驗證
至少包含：
- migration 後 schema 檢查
- 受影響 flow smoke test
- `python dev_guard/run_local_guard.py`
- 相關 UI 操作驗證

## 輸出格式
### 分析版
- 關鍵檔案
- 現況資料流
- target contract
- diff 清單
- 單一路徑執行方案
- 風險點

### 執行版
- 任務名稱
- 原則
- Step 1 / Step 2 / Step 3
- 修改檔案
- 驗證方式
- 禁止事項

## 禁止事項
- 不可跳過 contract 定義直接修 bug
- 不可一邊改 DB 一邊隨機補 code
- 不可未掃描引用就 rename / delete
- 不可擴大成整體重構
