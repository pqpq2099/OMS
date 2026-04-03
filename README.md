# OMS｜營運管理系統

**OMS（Operations Management System）** 是一套專為餐飲現場設計的叫貨決策支援系統。

> 定位：不是 ERP，不是財務系統。
> 核心價值：協助現場做出正確的叫貨判斷，並作為門市訓練工具。

---

## 功能範圍

| 流程 | 說明 |
|------|------|
| 盤點 | 記錄各門市現有庫存數量 |
| 建立訂單 | 依盤點結果產生叫貨清單 |
| 確認訂單 | 審核訂單內容後發送給廠商 |
| 指定交期 | 設定預計到貨日期 |

> 不含：收貨驗收、退貨、財務對帳

---

## 技術架構

| 項目 | 內容 |
|------|------|
| 語言 | Python 3.12 |
| 前端框架 | Streamlit |
| 資料庫 | Supabase（PostgreSQL） |
| 對外確認 | LINE Messaging API |

### 分層原則

```
pages    →  UI 顯示、收集輸入、觸發動作（不做計算、不寫資料）
logic    →  商業邏輯、驗證、組裝 view model
services →  讀寫資料庫、快取管理
shared   →  跨模組共用（RPC、LINE、報表計算、稽核）
```

---

## 模組說明

| 模組 | 負責範圍 |
|------|---------|
| `operations/` | 盤點、叫貨、叫貨明細、歷史紀錄 |
| `analysis/` | 報表、歷史分析、庫存比對 |
| `data_management/` | 品項、廠商、單位、換算率、價格設定 |
| `users_permissions/` | 使用者管理、角色、分店權限、個人帳號 |
| `system/` | 系統設定、外觀、維護工具 |
| `shared/` | 共用服務、RPC、LINE 推播、稽核紀錄 |
| `dev_guard/` | 本機驗證與防呆工具 |

---

## 快速啟動

```bash
# 安裝依賴
pip install -r requirements.txt

# 啟動應用
streamlit run app.py
```

環境變數請設定於 `.env`（參考 `.env.example`）：

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
LINE_CHANNEL_ACCESS_TOKEN=your-line-token
```

---

## 核心規則

- **「儲存並同步」** = 建立訂單（寫入資料庫）
- **「發送到 LINE」** = 最終確認（唯一對外確認點）
- 所有品項清單固定依 `item_id` 排序，不可變動
- UI 不做計算、不做驗證、不直接寫資料

---

## 版本狀態

| 項目 | 內容 |
|------|------|
| 目前版本 | v1.0 |
| 分支 | `develop`（開發）、`main`（穩定） |
| 資料庫 | Supabase（PostgreSQL） |
| 驗證狀態 | dev_guard PASS |

---

## 授權

私有專案，僅供內部使用。
