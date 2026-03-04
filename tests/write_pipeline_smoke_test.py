print("== write pipeline smoke test ==")

from data.repository_gsheets import GoogleSheetsRepo, RepoConfig
from core.audit_writer import AuditWriter
from core.id_generator import IdGenerator
from core.write_pipeline import WritePipeline

KEY_PATH = "secrets/service_account.json"
SHEET_ID = "1L1ogNjLWjjH8usMWC2JQowMMZkfD4zkuE-4UcgiTqXQ"

repo = GoogleSheetsRepo(KEY_PATH, RepoConfig(sheet_id=SHEET_ID, env="prod"))

# audit 先寫到 test 表
audit = AuditWriter(repo, sheet_name="audit_log_test")

id_gen = IdGenerator(repo, env="prod")

pipe = WritePipeline(repo, id_gen, audit_writer=audit, env="prod")

# 你 items 表要有基本欄位（至少 item_id / env / is_active / created_at...）
res = pipe.create(
    table="items",
    entity_key="items",
    id_field="item_id",
    actor_user_id="OWNER",
    payload={
        "item_name_zh": "測試品項",
        "item_name_en": "TEST ITEM",
    },
    note="write_pipeline smoke test",
)

print("✅ create ok:", res)
input("press enter to exit...")
