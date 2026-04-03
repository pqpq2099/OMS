---
name: oms-verification-smoke-test
description: 當任務完成後，需要用固定驗證步驟確認未破壞 OMS 主流程時，使用這個 Skill。
---

# OMS Verification Smoke Test

## 何時使用
- 任務修改完成後
- migration 套用後
- 模組拆分後
- bugfix 完成後
- 使用者要求「確認全部能跑」時

## 核心原則
1. 驗證不是附帶，是正式步驟
2. 先跑通用 guard，再跑任務專屬流程
3. 要驗證「原功能還活著」，不是只驗證「新改的地方沒報錯」
4. 驗證結果要可追蹤、可回報

## 通用驗證步驟
### Step 1：靜態檢查
- 搜尋殘留舊 key / 舊函式 / 舊路徑
- 檢查 import 是否斷裂
- 檢查修改檔是否有明顯語法錯誤

### Step 2：guard
執行：
```bash
python dev_guard/run_local_guard.py
```
記錄：
- compileall
- import smoke
- router smoke
- pages 邊界違規

### Step 3：模組 smoke test
依任務選擇相對應流程驗證。

#### 採購設定模組
至少驗：
- `page_purchase_settings` 可開啟
- vendors / items / prices / units / unit_conversions 可讀取
- 新增 / 編輯流程可正常通過
- require_price=false 不會炸

#### 叫貨模組
至少驗：
- 選店 → 選廠商 → 叫貨頁可進入
- 建議量、庫存欄位、結果頁可開
- order result / stock order record 不報錯

#### 歷史 / 分析
至少驗：
- 報表頁可開
- operation_date 路徑正常
- 不因 schema 變動而失敗

### Step 4：資料正確性驗證
若任務牽涉 DB / payload：
- 實際寫入欄位正確
- nullable / default / bool / numeric 正常
- 沒有 NaN / inf / JSON / key mismatch

### Step 5：回報
用固定格式輸出：
1. 驗證範圍
2. 執行命令
3. 結果摘要
4. 失敗項目
5. 是否可交付
6. 若不可交付，卡在哪一步

## 建議驗證順序
1. 單檔 / 單模組靜態檢查
2. dev_guard
3. 直接影響流程
4. 相鄰流程
5. DB / payload 實測

## 禁止事項
- 不可只說「理論上可用」
- 不可只跑 compile 不跑流程
- 不可 guard fail 但照樣宣稱完成
- 不可省略失敗項目
