from __future__ import annotations

from datetime import datetime
import json

import streamlit as st

from shared.services.service_id import allocate_audit_id
from shared.services.service_sheet import sheet_append, sheet_get_header


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def audit_log(action: str, entity_id: str, before: dict | None, after: dict | None, note: str = ""):
    try:
        try:
            audit_id = allocate_audit_id()
        except Exception:
            audit_id = f"AUDIT_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        row = {
            "audit_id": audit_id,
            "ts": _now_ts(),
            "user_id": st.session_state.get("login_user", ""),
            "action": action,
            "table_name": "users",
            "entity_id": entity_id,
            "before_json": json.dumps(before or {}, ensure_ascii=False),
            "after_json": json.dumps(after or {}, ensure_ascii=False),
            "note": note,
        }
        header = sheet_get_header("audit_logs")
        sheet_append("audit_logs", header, [row])
    except Exception:
        pass
