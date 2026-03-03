# core/id_generator.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class IdResult:
    new_id: str
    new_seq_value: int


class IdGeneratorError(Exception):
    pass


class IdGenerator:
    """
    ID generator backed by id_sequences table (Google Sheet table).
    - Each entity has an id prefix + zero-padded sequence number.
    - We update id_sequences atomically via repository layer (best-effort lock).
    """

    def __init__(
        self,
        repo,
        *,
        env: str = "prod",
        tz_offset_hours: int = 8,
        default_width: int = 6,
    ):
        """
        repo: your data repository object. Must implement:
          - get_id_sequence(key: str, env: str) -> Optional[dict]
          - upsert_id_sequence(key: str, env: str, next_value: int, updated_at: str, updated_by: str) -> None
          - try_lock(key: str, env: str, owner: str, ttl_sec: int = 15) -> bool   (optional)
          - unlock(key: str, env: str, owner: str) -> None                        (optional)

        id_sequences row schema assumed:
          key, prefix, width, next_value, env, updated_at, updated_by
        """
        self.repo = repo
        self.env = env
        self.tz_offset_hours = tz_offset_hours
        self.default_width = default_width

    # ----------------------------
    # Public API
    # ----------------------------
    def next_id(self, key: str, *, actor_user_id: str) -> IdResult:
        """
        Generate next ID for a given key (e.g. 'items', 'vendors', 'prices', 'stores', 'brands', 'units').

        Returns: IdResult(new_id, new_seq_value)
        """
        key = (key or "").strip()
        if not key:
            raise IdGeneratorError("key is required")

        # Optional lock (recommended). If your repo doesn't support it, it will skip.
        owner = f"{actor_user_id}:{key}:{self._now_iso()}"
        locked = self._try_lock(key, owner)
        try:
            row = self.repo.get_id_sequence(key=key, env=self.env)
            if not row:
                raise IdGeneratorError(f"id_sequences missing key='{key}' env='{self.env}'")

            prefix = str(row.get("prefix") or "").strip()
            width = int(row.get("width") or self.default_width)
            next_value = int(row.get("next_value") or 1)

            new_id = self._format_id(prefix, next_value, width)

            # increment and write back
            new_next_value = next_value + 1
            self.repo.upsert_id_sequence(
                key=key,
                env=self.env,
                next_value=new_next_value,
                updated_at=self._now_iso(),
                updated_by=actor_user_id,
            )

            return IdResult(new_id=new_id, new_seq_value=next_value)
        finally:
            if locked:
                self._unlock(key, owner)

    # ----------------------------
    # Helpers
    # ----------------------------
    def _format_id(self, prefix: str, seq: int, width: int) -> str:
        if not prefix:
            raise IdGeneratorError("prefix is empty in id_sequences")
        if seq <= 0:
            raise IdGeneratorError("sequence must be positive")
        return f"{prefix}{str(seq).zfill(width)}"

    def _now_iso(self) -> str:
        # Use UTC+8 by default (Asia/Taipei). Store ISO string.
        dt = datetime.now(timezone.utc)
        # manual offset without external libs
        offset_sec = self.tz_offset_hours * 3600
        dt_local = dt.timestamp() + offset_sec
        dt2 = datetime.fromtimestamp(dt_local, tz=timezone.utc)  # keep 'Z' semantics stable
        return dt2.replace(tzinfo=None).isoformat(timespec="seconds")

    def _try_lock(self, key: str, owner: str) -> bool:
        fn = getattr(self.repo, "try_lock", None)
        if callable(fn):
            try:
                return bool(fn(key=key, env=self.env, owner=owner, ttl_sec=15))
            except Exception:
                # if lock mechanism fails, do not block generation; rely on single-admin assumption
                return False
        return False

    def _unlock(self, key: str, owner: str) -> None:
        fn = getattr(self.repo, "unlock", None)
        if callable(fn):
            try:
                fn(key=key, env=self.env, owner=owner)
            except Exception:
                pass
