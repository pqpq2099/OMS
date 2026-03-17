# ORIVIA OMS 系統結構說明

## 1. 整體資料流

```
登入 / Sidebar
↓
Page（pages）
↓
Service（services）
↓
Data（data）
↓
Google Sheets
```

## 2. 分層職責

- `app.py`：系統入口、Sidebar、Router、登入狀態與全域流程。
- `pages/`：畫面呈現、表單輸入、按鈕操作。
- `services/`：商業邏輯、驗證、流程整理。
- `data/`：資料讀寫、查詢、與 Google Sheets 溝通。
- `core/`：ID 產生、Audit Log、寫入流程等核心能力。
- `utils/`：格式化、單位換算、輔助工具。

## 3. 主要功能區

- 作業：叫貨 / 庫存 / 盤點 / LINE 訊息。
- 分析：叫貨明細、進銷存分析、進貨分析。
- 資料管理：分店、廠商、品項、價格、單位等主資料。
- 使用者與權限：帳號、角色、分店範圍、升遷調整。
- 系統：外觀、資訊、成本檢查、系統工具。

## 4. 權限原則

目前專案以 `role + store_scope + is_active` 為主，不走複雜 ACL。

- `owner`：最高權限。
- `admin`：管理主資料與多數後台。
- `store_manager`：分店營運管理。
- `leader`：現場帶班與操作。
- `staff`：基本操作。
