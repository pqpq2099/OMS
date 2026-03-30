# OMS 壓測封版報告

## 一、Current Performance Baseline
系統在完成多輪優化與 benchmark 重跑後，已達穩定 baseline：
- cold path：初始化成本存在但已可控
- warm path：主要流程已收斂，無明顯重複計算
- 使用者操作流程（叫貨 / 報表）皆維持流暢

## 二、壓力測試結果
整體趨勢：
- 1x：穩定、即時回應
- 3x：無明顯延遲堆積
- 10x：開始出現計算堆疊，但仍可接受
- 30x：主要壓力集中於報表組裝與資料讀取，但未崩潰

結論：
系統具備可擴展性，未出現結構性瓶頸

## 三、Cold / Warm 熱點排序

### Cold Path（初始化）
1. load_report_shared_tables
2. spreadsheet backend 讀表
3. build_analysis_page_view_model（初次）

### Warm Path（操作）
1. build_analysis_page_view_model
2. build_history_page_view_model
3. _build_inventory_history_summary_df

## 四、已完成優化清單
- report upstream 共用結果抽取
- history / analysis 重複計算消除
- summary / detail 前置資料共用
- warm path cache 收斂
- DataFrame 組裝減少重複

## 五、Remaining Bottleneck（可接受）
- spreadsheet backend IO 仍為主要成本
- analysis page view model 組裝成本仍高
- 大型 DataFrame merge 在高倍壓力下仍存在耗時

## 六、封版判定

### 是否 warm 優化完成
是，warm path 已無結構性重複計算

### 是否可封版
是，目前版本可視為穩定可封版版本

### 未來唯一優化建議
優先優化：report shared tables 載入（IO 層）

