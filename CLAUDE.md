# CLAUDE.md

## 0. Session 開始時必讀（記憶恢復）

每次新 session 開始，請先讀取以下兩個檔案以恢復工作狀態：

- `F:\Google Backup\Claude Code\SESSION_MEMORY.md`（目前進度、待處理項目）
- `F:\Google Backup\Claude Code\DECISIONS_LOG.md`（重要技術決策記錄）

讀取後，向使用者簡短報告目前狀態，再詢問接下來要做什麼。

---

## 0. 環境對應（強制確認，執行任何 DB 操作前必讀）

| Git Branch | 目錄 | Supabase 專案 | Project ID |
|------------|------|--------------|------------|
| `main` | `OMS-main\` | OMS_V1（**正式環境**） | `usaaduuqhvpfmrmimwsw` |
| `develop` | `OMS-develop\` | OMS_TEST（**測試環境**） | `hikmpynwpqtbgqhsuyqd` |

**規則：**
- 對 `develop` branch 執行 DB 操作，必須使用 `hikmpynwpqtbgqhsuyqd`
- 對 `main` branch 執行 DB 操作，必須使用 `usaaduuqhvpfmrmimwsw`
- 每次執行 Supabase MCP 前，先確認目前在哪個 branch，再選正確的 project_id
- 不確定時，先執行 `git branch` 確認

---

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

## 3. 執行與輸出規則
> 通用規則（最小修改、單一方案、禁止腦補等）見 `~/.claude/CLAUDE.md`。
> 輸出格式見 `@docs/AI_OUTPUT_STANDARD.md`。
> 任務流程見 `/task-execution` skill。

本專案補充：
- 切新邏輯時，先保留舊接口 → 建橋接層 → 驗證穩定後再清理
- 任何 rename / delete 前，必須先搜尋全專案引用，列出上下游影響
- 未掃描引用就 rename / delete → 禁止
- 還沒驗證就清理 legacy → 禁止

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

## 8. 驗證與 dev_guard
> 驗證格式見 `dev_guard/VALIDATION_OUTPUT_TEMPLATE.md`。
> 交付檢查見 `/final-check` skill。

修改完成後必須跑：
```bash
python dev_guard/run_local_guard.py
```
若失敗，不可忽略，須說明哪項失敗、是否與本次修改相關、修正策略。

## 9. 檔案規模
單檔控制在 800–1000 行以下。過大時優先拆 logic / service，不為好看而大規模重構。

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

## 12. 禁止事項（OMS 專屬補充）
> 通用禁止事項見 `~/.claude/CLAUDE.md`。

- 不可直接刪 legacy，除非已確認無引用且驗證完成
- 不可憑感覺推測 schema 或 payload
- 不可跳過 dev_guard 驗證

## 13. 封版狀態（2026-04-02）
系統已於 2026-04-02 完成 v1.0 封版。
Tag: oms-v1.0-baseline (46b3d3b)
HEAD: 936cd0f (含 Cleanup C1/C2/C3)
dev_guard: 全項 PASS

進入維運 / 控制模式。
所有修改必須符合維運規則。
非 blocker bug 不得直接動 develop 核心模組。
