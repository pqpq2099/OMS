# OMS-main 進度交接檔

最後更新：2026-04-26

> Streamlit 主系統（Python）。對應 Supabase OMS_V1（main branch，正式）/ OMS_TEST（develop branch，測試）。Next.js 重寫版見 `OMS_V3/docs/PROGRESS.md`。

---

## 當前狀態

**v1.0 已封版**（2026-04-02），進入維運 / 控制模式。
- Tag：`oms-v1.0-baseline`（46b3d3b）
- HEAD：`936cd0f`（含 Cleanup C1/C2/C3）
- dev_guard：全項 PASS

非 blocker bug 不直接動 develop 核心模組；新功能優先評估在 OMS_V3 實作。

---

## 環境

| Branch | 目錄 | DB | 用途 |
|---|---|---|---|
| `main` | `OMS-main/` | OMS_V1（`usaaduuqhvpfmrmimwsw`）| 正式 |
| `develop` | `OMS-main/`（同 working tree，git checkout 切）| OMS_TEST（`hikmpynwpqtbgqhsuyqd`）| 測試 |

GitHub repo：https://github.com/pqpq2099/OMS

---

## 已完成（依主題）

### 權限系統（最大改造）
- Stage 1–4 全完成：DB tables + service + utility + 頁面守衛 + 門市範圍過濾
- 應用層權限（不啟用 RLS）：`permissions` / `role_permissions` / `user_store_scope` 三表
- Permission key 3-part 格式：`{domain}.{resource}.{action}`（migration 027）
- PERM_005 清理（migration 028），系統管理唯一 key = PERM_017
- 四層一致性掃描完成：role_permissions → sidebar → router → page guard 對齊
- P1 page guard 補齊：cost_debug / purchase_settings 等
- Role 字串 guard 轉換 5 頁：appearance / system_info / system_maintenance / system_tools / store_admin
- user_admin guard/context 分離：`require_permission` + `build_user_admin_context`
- 正式文件 `out/檔案現況_基本資料/OMS_權限系統正式文件_v1.md` 已產出

### 業務功能
- 叫貨主流程：盤點 + 叫貨單一入口（page_order）；LINE 送出 = 最終 confirm（draft → confirmed）
- 庫存調整模組：UI + logic + service，雙寫 stocktakes(manual_adjustment) + stock_adjustments
- 調貨模組：跨店 stock_transfers + stock_transfer_lines + 雙 stocktakes(transfer_out/in)
- 調貨廠商篩選：分店下方加廠商下拉，前端篩品項
- 系統備份功能：`system/pages/page_backup.py`，Excel 17 sheet（交易 9 + 主資料 8）
- 使用量換算頁：外送平台報表 → 配方展開 → 半成品拆解 → 包裝規格轉換
- 歷史叫貨紀錄：單一日期模式
- 進銷存分析：期間 / 單日雙模式

### Migration（OMS_TEST + OMS_V1 雙環境同步）
| Migration | 內容 |
|---|---|
| 018 / 019 / 020 | DB index 優化（移重複、補 FK 覆蓋）|
| 022 | OMS_V1 anon policy 清理 |
| 023 | OMS_TEST anon policy 清理 + service_role policy 改名統一 |
| 024 | RPC audit before/after_json 重套 jsonb（修 015 退化）|
| 025 / 026 | 庫存調整 + 調貨：3 張新表 + RLS + PERM_018/019 + role_permissions + id_sequences |
| 027 | Permission key 3-part 格式統一 |
| 028 | PERM_005 清理 |

### RLS（Phase 1）
- 25 張表全啟用 RLS + service_role bypass policy
- security advisor 0 ERROR
- Phase 2（細緻 policy）等接 Supabase Auth 後做

### Bug 修復
- audit_logs：`_write_audit_log` 改 Supabase insert + actor fallback（login_user → store_<id> → unknown）
- id_allocation：line 51 str→int 修 dtype 'int64' 錯
- 叫貨明細排序：sort_values 第三鍵 item_name → item_id
- itertuples 底線欄位 bug：`_target_date` 等改名
- 期間消耗錨點：prev_date 可穿越查詢起始邊界
- fetch_table 1000 筆上限：分頁迴圈修復
- 庫存金額顯示：無進貨廠商正確顯示
- actor 一致性稽核 + 全系統 item_id 排序修正

### 架構 / 工具
- `/load` + `/update` skills 建立（session 讀取 / 交接更新固定指令）
- 子專案 CLAUDE.md 補環境對應表（branch → DB）
- 文件一致性收斂：必讀清單統一 2 份、孤兒文件歸檔
- weekly_optimize 報告路徑改 `docs/reports/weekly_YYYYMMDD.md`
- dual-push skill Co-Author 升 4.7

---

## 待處理（OMS-main 範疇）

| 優先 | 項目 | 說明 |
|---|---|---|
| 中 | 使用量換算頁優化 | 配方表目前讀本地 Excel；未來可寫入 DB（migration）；半成品子原料 mapping 目前 hardcode 在 logic 中 |
| 低 | stocktake 功能正式化 | 需補 route/export，現已退出正式系統 |
| 低 | RLS Phase 2 | 接 Supabase Auth 後設細緻 policy |
| 低 | OMS_V1 亂碼資料掃描 | 同樣 BIG5 編碼壞掉問題在 V1 是否存在未確認（2026-04-26 只清了 OMS_TEST 7 列）|

---

## 已知議題 / 風險

1. **單一 working tree 雙 branch**：2026-04-25 起 main + develop 共用 `OMS-main/` 工作目錄，以 `git checkout` 切換。執行 DB 操作前必須先 `git branch` 確認對應環境，再選正確 project_id。
2. **OMS_V1 編碼壞掉資料**：歷史 BIG5 → UTF-8 寫入錯誤導致部分 item_name / unit 為 `�` 替代字元。OMS_TEST 已清完，OMS_V1 未掃描。
3. **使用量換算頁配方表**：目前讀本地 Excel，無 DB 持久化；半成品 mapping hardcode 在 logic。
4. **dev_guard 必跑**：任何修改後必須跑 `python dev_guard/run_local_guard.py`，失敗不可忽略。

---

## 檔案結構（重點段落）

```
OMS-main/
├── operations/                  ← 現場作業（叫貨/庫存/調貨/調整）
│   ├── pages/                   ← UI（不寫資料、不大型處理）
│   ├── logic/                   ← 流程、判斷、view model
│   └── services/                ← Supabase 讀寫
├── analysis/                    ← 報表 / 查詢
│   ├── pages/
│   └── logic/
├── data_management/             ← 主資料 + 採購設定
├── users_permissions/           ← 帳號 / 角色 / 門市權限
├── system/                      ← 維護工具（含 page_backup.py）
├── shared/
│   ├── services/                ← 跨模組 Supabase 服務
│   └── utils/permissions.py     ← require_permission 入口
├── supabase/migrations/         ← 028 個 migration
├── dev_guard/                   ← 本機驗證 + 防呆
└── CLAUDE.md / AGENTS.md        ← 入口規則（鎖死）
```

---

## 紅線（OMS-main 專屬）

- **嚴格分層**：page 只做 UI；logic 做業務；service 做 Supabase；shared 跨模組
- **page 禁止**：直接寫資料 / 大型資料處理 (merge/groupby/map/drop_duplicates) / schema 修補
- **排序規則**：所有品項列表一律依 `item_id` 升序，不可因條件改變
- **單位規則**：計算以 `base_qty` 為準，UI 可輸入操作單位（包/箱）
- **價格規則**：`require_price=false` 是正式制度；安全落 0，不可造 NaN/inf
- **actor 規則**：`actor / created_by / updated_by` 統一用 `login_user`（user_id），不可用 role 字串
- **任何修改完成必跑 dev_guard**

---

## 連結

- 跨模組摘要：`SESSION_MEMORY.md`
- 任務簡報：`docs/TASK_BRIEF.md`
- AI 交接：`docs/AI_HANDOFF.md`
- 規則細節：`docs/MASTER_RULES.md`
- 系統基準：`docs/SYSTEM_BASELINE.md`
- 自動化流程：`docs/AUTOMATION_WORKFLOW.md`
- 權限文件：`out/檔案現況_基本資料/OMS_權限系統正式文件_v1.md`
- DB schema：`out/檔案現況_基本資料/OMS_DB_SCHEMA_正式文件_v1.md`
- 決策記錄：`DECISIONS_LOG.md`
- V3 重寫版進度：`OMS_V3/docs/PROGRESS.md`
