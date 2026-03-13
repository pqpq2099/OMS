"""
核心模組：寫入流程管線。
用來整理資料寫回 Google Sheets 的流程。
"""

# core/write_pipeline.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from core.audit_writer import AuditWriter, AuditEvent


@dataclass(frozen=True)
class WriteResult:
    table: str
    entity_id: str
    action: str


class WritePipeline:
    """
    Minimal write pipeline:
    - create row (with generated id)
    - write to sheet
    - write audit log
    """

    def __init__(self, repo, id_generator, audit_writer: AuditWriter, *, env: str = "prod"):
        self.repo = repo
        self.id_gen = id_generator
        self.audit = audit_writer
        self.env = env

    # ----------------------------
    # Public API
    # ----------------------------
    def create(
        self,
        *,
        table: str,
        entity_key: str,               # e.g. "items"
        id_field: str,                 # e.g. "item_id"
        actor_user_id: str,
        payload: Dict[str, Any],
        note: str = "",
    ) -> WriteResult:
        """
        entity_key is used by id_sequences, table is worksheet name.
        payload is user-provided fields (excluding id_field).
        """
        new_id = self.id_gen.next_id(entity_key, actor_user_id=actor_user_id).new_id

        row = dict(payload)
        row[id_field] = new_id
        row.setdefault("env", self.env)
        row.setdefault("is_active", "TRUE")
        row.setdefault("created_at", self.repo.now_iso())
        row.setdefault("created_by", actor_user_id)
        row.setdefault("updated_at", self.repo.now_iso())
        row.setdefault("updated_by", actor_user_id)

        # write row to db
        self.repo.append_row(table, row)

        # audit
        self.audit.write(
            AuditEvent(
                action="create",
                table=table,
                entity_id=new_id,
                actor_user_id=actor_user_id,
                env=self.env,
                before=None,
                after=row,
                note=note,
            )
        )

        return WriteResult(table=table, entity_id=new_id, action="create")
