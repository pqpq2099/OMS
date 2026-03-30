# dev_guard 使用說明

所有修改後必須執行：

python dev_guard/run_local_guard.py

目的：
- 防止錯誤 import
- 防止函數缺失
- 防止命名錯誤
- 確認最小修改未擴散

此步驟不可跳過。

建議流程：
1. 先輸出分析版
2. 再輸出執行版
3. 依執行版修改
4. 修改後執行 dev_guard
