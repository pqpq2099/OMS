from data.repository_gsheets import GoogleSheetsRepo, RepoConfig

KEY_PATH = "secrets/service_account.json"
SHEET_ID = "1L1ogNjLWjjH8usMWC2JQowMMZkfD4zkuE-4UcgiTqXQ"

repo = GoogleSheetsRepo(KEY_PATH, RepoConfig(sheet_id=SHEET_ID, env="prod"))
df = repo.read_table("id_sequences")
print("columns:", list(df.columns))
print(df.head(3))
