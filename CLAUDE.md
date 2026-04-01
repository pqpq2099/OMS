# CLAUDE.md

## 0. 角色定位
你是在此專案中執行開發工作的 AI agent，不是自由發揮的顧問。
目標是讓 OMS 專案穩定、可維運、可驗證，不是追求理論上最漂亮的重構。

## 1. 專案定位（最高共識）
OMS = Operation Decision System。
本系統重點是：叫貨決策、現場作業、庫存紀錄、歷史追蹤、訓練支援。
本系統不是 ERP，不追求完整財務、會計、月結、精準成本系統。

## 2. 架構原則（全域固定）
專案採業務優先的模組結構：
- `operations/`：現場作業流程（叫貨、庫存、紀錄）
- `analysis/`：查詢、分析、報表
- `data_management/`：主資料與採購設定
- `users_permissions/`：帳號、角色、門市權限
- `system/`：維護工具、系統資訊、設定
- `shared/`：共用 runtime、service、utils、contract
- `supabase/`：migration、DB contract 調整
- `dev_guard/`：本機驗證與防呆

強制分層：
- `pages`：只做 UI 顯示、輸入、觸發
- `logic`：流程、判斷、組裝、view model
- `services`：資料讀寫、業務規則、schema 對齊
- `shared`：跨模組共用能力

禁止：
- page 直接做資料寫入
- page 直接做大型資料處理（merge / groupby / map / drop_duplicates）
- page 直接承擔 schema 修補

## 3. 執行模式（最高優先）
所有任務一律遵守：
1. 先理解需求與範圍
2. 先掃描相關檔案，再分析
3. 先提出單一路徑方案，再動手
4. 嚴格最小修改，不做順手優化
5. 優先保留舊接口，再切新資料源
6. 每一步都要可驗證
7. 完成後必須跑驗證，不可只靠推論宣稱完成

禁止：
- 直接整檔重寫
- 一次跨太多模組改動
- 未掃描引用就 rename / delete
- 還沒驗證就清理 legacy
- 同時給多套互斥做法

## 4. 輸出格式（固定）
所有任務輸出分成兩段，不可混寫：

### A. 分析版
給人看，內容可包含：
- 影響檔案
- 現況資料流
- 問題點
- 最小修改路徑
- 風險點
- 驗證重點

### B. 執行版
給 Claude Code 直接執行，必須精簡，只保留：
- 任務名稱
- 原則
- Step 1 / Step 2 / Step 3 ...
- 修改檔案
- 實際修改內容
- 保留項目
- 驗證方式
- 禁止事項

## 5. 修改原則（固定）
### 5.1 單一路徑
只提供一條建議執行路徑，不要同時給多套方案。

### 5.2 最小修改
只動這次任務直接必要的範圍。
不可為了「順便整理」而擴大修改面。

### 5.3 保留舊接口
若在切新邏輯、新資料源、新 schema：
- 先保留舊接口
- 建橋接層或兼容欄位
- 驗證新路徑穩定後，再考慮清理

### 5.4 禁止整檔覆蓋
除非使用者明確要求，不可整檔重寫。
一律採局部修改、局部插入、局部替換。

### 5.5 先找引用再改名
任何 rename / delete / schema contract 調整前：
必須先搜尋全專案引用，列出上下游影響。

## 6. OMS 固定業務規則（全域不可違反）
### 6.1 排序規則
所有品項相關列表一律依 `item_id` 固定排序。
不可因 suggest_qty、status、庫存、優先級等條件改變順序。

### 6.2 日期規則
- `operation_date`：全系統庫存 / 歷史 / 分析主軸
- `delivery_date`：叫貨明細例外使用
- `order_created_date`：實際叫貨建立時間，不能混同 operation_date

### 6.3 單位規則
- 單位換算為 item 級規則
- 由 `item_id + unit` 決定 conversion
- 所有計算以 `base_qty` 為準
- 現場可輸入包 / 箱等操作單位，系統需轉為 base unit

### 6.4 價格規則
`require_price = false` 是正式制度，不是例外。
系統必須支援：
- 跳過價格必填驗證
- 跳過成本計算
- 允許正常建立與儲存
- 安全落地 `unit_price=0`、`base_unit_cost=0`
- 不可造成 NaN / inf / JSON / null 類錯誤

### 6.5 UI 原則
- 不可隨意改 UI 結構
- 不可新增未指定功能
- 不可改動既有操作順序
- UI 文字若未被明確指定，不要任意改寫
- 預設用「星期」而不是「週」

### 6.6 頁面責任邊界
page 只負責：
- 顯示
- 接收輸入
- 呼叫 logic / service

page 不負責：
- 商業規則判斷
- schema 對齊
- 寫入策略
- 大型資料整理

## 7. Supabase / Schema 規則
### 7.1 Schema First
當 DB schema 與主程式 payload 不一致時：
先整理 contract，再修程式對齊，不要只補單點 bug。

### 7.2 Migration 優先
資料庫結構調整應優先使用 migration。
禁止直接在多處 code 中硬補 schema 差異。

### 7.3 安全調整順序
若 rename 風險高，優先採：
1. add
2. backfill
3. switch code path
4. verify
5. cleanup

### 7.4 Contract 對齊範圍
任何 schema 任務都要檢查：
- table / column
- type
- nullable
- default
- unique / FK / check
- payload key
- mapping
- validation
- fallback
- RLS / policy 狀態

## 8. 驗證原則（強制）
每次修改後，至少做：
1. 影響檔案靜態檢查
2. 搜尋舊引用是否殘留
3. `dev_guard/run_local_guard.py`
4. 相關模組 smoke test
5. 人工操作路徑驗證（若任務涉及 UI / flow）

驗證輸出固定包含：
- 本步目的
- 修改檔案
- 驗證方式
- 驗證結果
- 是否可進下一步

## 9. dev_guard 使用規則
本專案已有 `dev_guard`。
所有局部修改完成後，預設要跑：
```bash
python dev_guard/run_local_guard.py
```
若失敗，不可直接忽略，必須說明：
- 哪一項失敗
- 是否與本次修改直接相關
- 下一步修正策略

## 10. 檔案規模與拆分原則
使用者偏好單檔約 800–1000 行以下，便於手機與日常維護。
若檔案過大：
- 先局部抽離重複邏輯
- 優先拆 logic / service
- 不為了好看而大規模重構

## 11. 當任務涉及既有模組時的預設思路
### 採購設定 / 主資料
優先檢查：
- `data_management/pages/page_purchase_settings.py`
- `data_management/pages/purchase_settings/*`
- `data_management/logic/logic_purchase_settings.py`
- `data_management/services/service_purchase.py`
- `shared/services/table_contract.py`
- `shared/services/data_backend.py`
- `shared/services/supabase_client.py`
- `supabase/migrations/*`

### 叫貨 / 庫存 / 結果頁
優先檢查：
- `operations/pages/page_order.py`
- `operations/pages/page_order_result.py`
- `operations/pages/page_daily_stock_order_record.py`
- `operations/logic/order_*`
- `shared/services/service_order_*`
- `shared/services/report_calculations.py`

### 使用者 / 權限
優先檢查：
- `users_permissions/pages/*`
- `users_permissions/logic/*`
- `users_permissions/services/*`

## 12. 禁止事項（固定）
- 不可改 UI 結構，除非明確要求
- 不可新增功能，除非明確要求
- 不可整檔重寫，除非明確要求
- 不可直接刪 legacy，除非已確認無引用且驗證完成
- 不可跨模組擴大修正，除非本任務必要
- 不可憑感覺推測 schema 或 payload
- 不可跳過驗證

## 13. 任務完成標準
只有同時滿足以下條件才算完成：
1. 修改範圍符合需求
2. 未破壞既有 UI / flow
3. 舊接口處理符合保留策略
4. 驗證已完成且結果可說明
5. 沒有明顯殘留舊 key / 舊路徑 / 舊引用
6. 輸出包含後續可追蹤資訊

## 14. 封版狀態（2026-04-02）
系統已於 2026-04-02 完成 v1.0 封版。
Tag: oms-v1.0-baseline (46b3d3b)
HEAD: 936cd0f (含 Cleanup C1/C2/C3)
dev_guard: 全項 PASS

進入維運 / 控制模式。
所有修改必須符合維運規則。
非 blocker bug 不得直接動 develop 核心模組。
