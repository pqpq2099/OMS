# ORIVIA OMS 檔案結構說明

這份說明是給「不以程式語言為主」的人看的。
之後如果你忘記某個功能大概在哪裡，先看這份。

## 1. 專案主入口

- `app.py`：整個 Streamlit 系統的入口。
  - 管理 sidebar
  - 管理 step/router
  - 決定現在要顯示哪個頁面

- `oms_core.py`：全系統共用函式。
  - 讀表
  - 共用樣式
  - 共用資料整理
  - 報表/畫面常用輔助函式

## 2. pages/ 畫面層

這裡放「使用者看得到的頁面」。

- `pages/page_order_entry.py`：分店選擇、廠商選擇、叫貨主頁、LINE 訊息明細
- `pages/page_reports.py`：報表與分析
- `pages/page_purchase_settings.py`：採購設定入口
- `pages/page_stocktake.py`：盤點頁
- `pages/page_user_admin.py`：使用者權限頁

## 3. services/ 服務層

這裡放「介於畫面與資料之間的業務邏輯」。
簡單理解：不是純畫面，也不是純資料，而是流程邏輯。

## 4. data/ 資料層

這裡放「怎麼讀寫 Google Sheets」。
之後如果你想找：
- 哪裡在讀表
- 哪裡在寫表
- 哪裡在查詢資料

優先看這裡。

## 5. core/ 核心流程

這裡放比較底層、比較系統級的功能，例如：
- audit log
- ID 產生
- 寫入流程

## 6. utils/ 工具層

這裡放共用小工具。
最重要的是：
- `utils_units.py`：單位換算

## 7. tests/ 測試

這裡放測試檔。
之後如果系統哪裡怪怪的，可以先從這裡做檢查。

## 8. 這次整理做了什麼

1. 把舊的根目錄 `pages_*.py` 正式搬進 `pages/`
2. 補上 `pages/__init__.py`
3. 把 `page_purchase_settings.py` 獨立出來
4. 更新 `app.py` 匯入路徑
5. 讓 `user_admin` 路由直接接上真正的頁面函式
6. 移除 `_archive_old`、`_archive_old_pages`、舊版根目錄頁面檔
7. 加上中文模組說明，方便之後對照
