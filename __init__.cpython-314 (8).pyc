# ============================================================
# ORIVIA OMS
# 檔案：tests/audit_smoke_test.py
# 說明：Audit 快速測試
# 功能：驗證 audit log 寫入流程是否可正常執行。
# 注意：屬測試用途。
# ============================================================

"""測試檔：驗證 audit_log 是否可成功寫入測試表。"""

print("== audit smoke test ==")

from data.repository_gsheets import GoogleSheetsRepo, RepoConfig
from core.audit_writer import AuditWriter, AuditEvent

KEY_PATH = "secrets/service_account.json"
SHEET_ID = "1L1ogNjLWjjH8usMWC2JQowMMZkfD4zkuE-4UcgiTqXQ"

repo = GoogleSheetsRepo(KEY_PATH, RepoConfig(sheet_id=SHEET_ID, env="prod"))
audit = AuditWriter(repo, sheet_name="audit_log_test")

ev = AuditEvent(
    action="test",
    table="system",
    entity_id="SMOKE",
    actor_user_id="OWNER",
    env="prod",
    before={"hello": "world"},
    after={"ok": True},
    note="audit_log write smoke test",
)

audit.write(ev)

print("✅ wrote 1 row into audit_log_test")
input("press enter to exit...")
