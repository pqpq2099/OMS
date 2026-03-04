from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AuditEvent:
    action: str                 # create/update/toggle
    table: str                  # vendors/items/prices/...
    entity_id: str              # item_id/vendor_id/...
    actor_user_id: str
    env: str = "prod"
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    note: str = ""


class AuditWriter:
    def __init__(self, repo, *, sheet_name: str = "audit_log_test"):
        self.repo = repo
        self.sheet_name = sheet_name

    def write(self, ev: AuditEvent) -> None:
        row = {
            "ts": self.repo.now_iso(),
            "env": ev.env,
            "action": ev.action,
            "table": ev.table,
            "entity_id": ev.entity_id,
            "actor_user_id": ev.actor_user_id,
            "before_json": "" if ev.before is None else str(ev.before),
            "after_json": "" if ev.after is None else str(ev.after),
            "note": ev.note,
        }
        self.repo.append_audit_log(row, sheet_name=self.sheet_name)
