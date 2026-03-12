"""測試檔：快速確認 Google Sheets 連線與 id_sequences 是否可讀。"""

print("== start ==")

from data.repository_gsheets import GoogleSheetsRepo, RepoConfig
from core.id_generator import IdGenerator

KEY_PATH = "secrets/service_account.json"
SHEET_ID = "1L1ogNjLWjjH8usMWC2JQowMMZkfD4zkuE-4UcgiTqXQ"

print("1) init repo...")
repo = GoogleSheetsRepo(KEY_PATH, RepoConfig(sheet_id=SHEET_ID, env="prod"))
print("2) connected, now:", repo.now_iso())

print("3) read id_sequences...")
df = repo.read_table("id_sequences")
print("4) id_sequences rows:", len(df))

print("5) gen id...")
gen = IdGenerator(repo, env="prod")
res = gen.next_id("items", actor_user_id="OWNER")
print("6) result:", res)

print("== end ==")
input("press enter to exit...")
