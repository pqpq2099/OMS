# core/id_generator.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class IdResult:
    new_id: str
    new_seq_value: int


class IdGeneratorError(Exception):
    pass


class IdGenerator:
    def __init__(self, repo, *, env: str = "prod", default_width: int = 6, tz_offset_hours: int = 8):
        self.repo = repo
        self.env = env
        self.default_width = default_width
        self.tz_offset_hours = tz_offset_hours

    def next_id(self, key: str, *, actor_user_id: str) -> IdResult:
        key = (key or "").strip()
        if not key:
            raise IdGeneratorError("key is required")

        row = self.repo.get_id_sequence(key=key, env=self.env)
        if not row:
            raise IdGeneratorError(f"id_sequences missing key='{key}' env='{self.env}'")

        prefix = str(row.get("prefix") or "").strip()
        width = int(row.get("width") or self.default_width)
        next_value = int(row.get("next_value") or 1)

        if not prefix:
            raise IdGeneratorError("prefix is empty in id_sequences")
        if next_value <= 0:
            raise IdGeneratorError("next_value must be positive")

        new_id = f"{prefix}{str(next_value).zfill(width)}"

        self.repo.upsert_id_sequence(
            key=key,
            env=self.env,
            next_value=next_value + 1,
            updated_at=self._now_iso(),
            updated_by=actor_user_id,
        )

        return IdResult(new_id=new_id, new_seq_value=next_value)

    def _now_iso(self) -> str:
        dt = datetime.now(timezone.utc)
        offset_sec = self.tz_offset_hours * 3600
        dt_local = dt.timestamp() + offset_sec
        dt2 = datetime.fromtimestamp(dt_local, tz=timezone.utc)
        return dt2.replace(tzinfo=None).isoformat(timespec="seconds")
