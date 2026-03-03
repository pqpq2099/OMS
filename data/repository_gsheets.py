# data/repository_gsheets.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials


class RepoError(Exception):
    pass


@dataclass(frozen=True)
class RepoConfig:
    sheet_id: str
    env: str = "prod"          # 'prod' or 'sandbox'
    tz_offset_hours: int = 8   # Asia/Taipei


class GoogleSheetsRepo:
    """
    Google Sheets repository for ORIVIA_OMS_DB.
    Assumes each worksheet is a table with header row in row 1.
    """

    def __init__(self, creds_json_path: str, config: RepoConfig):
        self.config = config
        self._gc = self._connect(creds_json_path)
        self._sh = self._gc.open_by_key(config.sheet_id)

    # ----------------------------
    # Connection
    # ----------------------------
    def _connect(self, creds_json_path: str) -> gspread.Client:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(creds_json_path, scopes=scopes)
        return gspread.authorize(creds)

    # ----------------------------
    # Time
    # ----------------------------
    def now_iso(self) -> str:
        dt = datetime.now(timezone.utc)
        offset_sec = self.config.tz_offset_hours * 3600
        dt_local = dt.timestamp() + offset_sec
        dt2 = datetime.fromtimestamp(dt_local, tz=timezone.utc)
        return dt2.replace(tzinfo=None).isoformat(timespec="seconds")

    # ----------------------------
    # Low-level helpers
    # ----------------------------
    def _ws(self, name: str):
        try:
            return self._sh.worksheet(name)
        except Exception as e:
            raise RepoError(f"worksheet not found: {name}") from e

    def read_table(self, table: str) -> pd.DataFrame:
        ws = self._ws(table)
        values = ws.get_all_values()
        if not values:
            return pd.DataFrame()

        header = values[0]
        rows = values[1:]
        # keep empty table
        if not rows:
            return pd.DataFrame(columns=header)

        df = pd.DataFrame(rows, columns=header)
        return df

    def append_row(self, table: str, row: Dict[str, Any]) -> None:
        ws = self._ws(table)
        header = ws.row_values(1)
        out = []
        for col in header:
            out.append("" if row.get(col) is None else str(row.get(col)))
        ws.append_row(out, value_input_option="USER_ENTERED")

    def upsert_by_pk(self, table: str, pk: str, entity: Dict[str, Any]) -> str:
        """
        Update if pk exists, else append.
        Returns action: 'update' | 'create'
        """
        ws = self._ws(table)
        header = ws.row_values(1)
        if pk not in header:
            raise RepoError(f"pk '{pk}' not found in table '{table}' header")

        pk_idx = header.index(pk) + 1

        pk_value = str(entity.get(pk, "")).strip()
        if not pk_value:
            raise RepoError(f"entity missing pk value: {pk}")

        # Find row by pk value (scan pk column)
        col_vals = ws.col_values(pk_idx)
        # col_vals[0] is header
        target_row = None
        for i, v in enumerate(col_vals[1:], start=2):
            if str(v).strip() == pk_value:
                target_row = i
                break

        # Build row aligned with header
        out = []
        for col in header:
            out.append("" if entity.get(col) is None else str(entity.get(col)))

        if target_row is None:
            ws.append_row(out, value_input_option="USER_ENTERED")
            return "create"
        else:
            # update entire row (simple + safe)
            ws.update(f"A{target_row}", [out], value_input_option="USER_ENTERED")
            return "update"

    # ----------------------------
    # id_sequences API (for IdGenerator)
    # ----------------------------
    def get_id_sequence(self, *, key: str, env: str) -> Optional[Dict[str, Any]]:
        df = self.read_table("id_sequences")
        if df.empty:
            return None

        # normalize
        k = key.strip()
        e = env.strip()

        # Columns assumed: key, prefix, width, next_value, env, updated_at, updated_by
        filt = df[(df.get("key") == k) & (df.get("env") == e)]
        if filt.empty:
            return None

        row = filt.iloc[0].to_dict()
        return row

    def upsert_id_sequence(
        self,
        *,
        key: str,
        env: str,
        next_value: int,
        updated_at: str,
        updated_by: str,
    ) -> None:
        # Upsert into id_sequences by composite pk (key+env).
        # Since Google Sheets has no composite pk, we do manual scan by both.
        ws = self._ws("id_sequences")
        header = ws.row_values(1)

        required = ["key", "env", "next_value", "updated_at", "updated_by"]
        for c in required:
            if c not in header:
                raise RepoError(f"id_sequences missing column: {c}")

        key_col = header.index("key") + 1
        env_col = header.index("env") + 1

        key_vals = ws.col_values(key_col)
        env_vals = ws.col_values(env_col)

        target_row = None
        for i in range(2, max(len(key_vals), len(env_vals)) + 1):
            kv = key_vals[i - 1] if i - 1 < len(key_vals) else ""
            ev = env_vals[i - 1] if i - 1 < len(env_vals) else ""
            if str(kv).strip() == key and str(ev).strip() == env:
                target_row = i
                break

        # Build current row dict from existing if found
        if target_row is not None:
            current = ws.row_values(target_row)
            cur_map = {header[j]: (current[j] if j < len(current) else "") for j in range(len(header))}
        else:
            cur_map = {h: "" for h in header}

        # Update fields
        cur_map["key"] = key
        cur_map["env"] = env
        cur_map["next_value"] = str(int(next_value))
        cur_map["updated_at"] = updated_at
        cur_map["updated_by"] = updated_by

        # Keep existing prefix/width if already present
        out = [cur_map.get(h, "") for h in header]

        if target_row is None:
            ws.append_row(out, value_input_option="USER_ENTERED")
        else:
            ws.update(f"A{target_row}", [out], value_input_option="USER_ENTERED")

    # ----------------------------
    # audit_log convenience
    # ----------------------------
    def append_audit_log(self, row: Dict[str, Any]) -> None:
        self.append_row("audit_log", row)
