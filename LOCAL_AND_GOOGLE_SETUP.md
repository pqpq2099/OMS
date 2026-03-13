# ORIVIA OMS 本機 / Google 試算表切換說明

## 1. 本機模式
請在啟動前設定環境變數：

- `ORIVIA_DATA_SOURCE=local`
- `ORIVIA_LOCAL_DB_PATH=ORIVIA_OMS_DB_TEST.xlsx`

如果沒有設定 `ORIVIA_LOCAL_DB_PATH`，系統會預設找專案根目錄的 `ORIVIA_OMS_DB_TEST.xlsx`。

## 2. Google 模式
請在啟動前設定：

- `ORIVIA_DATA_SOURCE=google`
- `ORIVIA_SHEET_ID=你的 Google Sheet ID`（可不設，則用程式預設值）

並準備：
- 本機 `service_account.json`，或
- Streamlit secrets 的 `gcp_service_account` / `SHEET_ID`

## 3. 這次已完成
- 刪除成本檢查入口與 router
- 採購設定正式接上
- 使用者權限正式接上
- settings 可本機 / Google 共用
