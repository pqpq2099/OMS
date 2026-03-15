# ============================================================
# ORIVIA OMS
# 檔案：tests/check_headers.py
# 說明：表頭檢查測試
# 功能：檢查資料表表頭是否與程式預期一致。
# 注意：適合用於資料庫結構驗證。
# ============================================================

"""測試檔：快速檢查某張工作表的欄位標頭。"""

from data.repository_gsheets import GoogleSheetsRepo, RepoConfig

KEY_PATH = "secrets/service_account.json"
SHEET_ID = "1L1ogNjLWjjH8usMWC2JQowMMZkfD4zkuE-4UcgiTqXQ"

repo = GoogleSheetsRepo(KEY_PATH, RepoConfig(sheet_id=SHEET_ID, env="prod"))
df = repo.read_table("id_sequences")
print("columns:", list(df.columns))
print(df.head(3))
