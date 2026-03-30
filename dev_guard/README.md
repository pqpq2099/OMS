# OMS 防呆自動化機制

本機防呆機制只新增驗證與控制，不改任何業務功能、不改 UI、不重構、不搬檔。

## 一、內容

- `dev_guard/run_local_guard.py`
  - 本機統一驗證入口
- `.pre-commit-config.yaml`
  - pre-commit 設定
- `.githooks/pre-commit`
  - git hook 等效方案
- `dev_guard/install_git_hook.sh`
  - 安裝 git hook
- `dev_guard/AI_DEVELOPMENT_CONTROL_TEMPLATE.md`
  - AI 開發控制模板
- `dev_guard/VALIDATION_OUTPUT_TEMPLATE.md`
  - 修改後標準輸出模板
- `dev_guard/latest_guard_report.json`
  - 最近一次驗證原始結果
- `dev_guard/latest_guard_report.md`
  - 最近一次驗證標準報告

## 二、檢查內容

每次執行會檢查：

1. compileall
2. import smoke
3. router smoke
4. pages/__init__.py 匯出檢查
5. page 邊界違規
   - page 不可直接呼叫 create_ / update_ / reset_ / send_
   - page 不可直接做 merge / groupby / map / drop_duplicates

## 三、使用方式

### 方式 A：手動執行

```bash
python dev_guard/run_local_guard.py
```

### 方式 B：git hook

```bash
bash dev_guard/install_git_hook.sh
```

安裝後，每次 commit 前會自動執行 guard；驗證失敗會直接阻擋提交。

### 方式 C：pre-commit

先安裝 pre-commit 套件，再執行：

```bash
pre-commit install
pre-commit run --all-files
```

## 四、標準輸出

執行後會產出：

- `dev_guard/latest_guard_report.json`
- `dev_guard/latest_guard_report.md`

其中 markdown 報告固定包含：

1. 執行資訊
2. 總結論
3. 失敗項目
4. 提交判定

## 五、通過標準

必須同時滿足以下條件才算 PASS：

- compileall 通過
- import smoke 無失敗
- router smoke 通過
- pages __init__ 匯出無失敗
- page 邊界違規為 0
