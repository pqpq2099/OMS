# data/repository_gsheets.py

from dataclasses import dataclass
from datetime import datetime, timezone
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd


@dataclass
class RepoConfig:
    sheet_id: str
    env: str = "prod"
    tz_offset_hours: int = 8


class GoogleSheetsRepo:
    def __init__(self, creds_json_path: str, config: RepoConfig):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(creds_json_path, scopes=scopes)
        gc = gspread.authorize(creds)
        self.sh = gc.open_by_key(config.sheet_id)
        self.config = config

    def now_iso(self):
        dt = datetime.now(timezone.utc)
        return dt.replace(tzinfo=None).isoformat(timespec="seconds")

    def read_table(self, table: str):
        ws = self.sh.worksheet(table)
        values = ws.get_all_values()
        if not values:
            return pd.DataFrame()
        header = values[0]
        rows = values[1:]
        return pd.DataFrame(rows, columns=header)

    def get_id_sequence(self, *, key: str, env: str):
        df = self.read_table("id_sequences")
        filt = df[(df["key"] == key) & (df["env"] == env)]
        if filt.empty:
            return None
        return filt.iloc[0].to_dict()

    def upsert_id_sequence(
        self,
        *,
        key: str,
        env: str,
        next_value: int,
        updated_at: str,
        updated_by: str,
    ):
        ws = self.sh.worksheet("id_sequences")
        rows = ws.get_all_values()
        header = rows[0]

        key_i = header.index("key")
        env_i = header.index("env")
        next_i = header.index("next_value")
        up_at_i = header.index("updated_at")
        up_by_i = header.index("updated_by")

        for r, row in enumerate(rows[1:], start=2):
            if row[key_i] == key and row[env_i] == env:
                ws.update_cell(r, next_i + 1, str(next_value))
                ws.update_cell(r, up_at_i + 1, updated_at)
                ws.update_cell(r, up_by_i + 1, updated_by)
                return

        # 找不到對應列：直接新增（Fail-fast 也可以改成 raise）
        new_row = {h: "" for h in header}
        new_row["key"] = key
        new_row["env"] = env
        new_row["next_value"] = str(int(next_value))
        new_row["updated_at"] = updated_at
        new_row["updated_by"] = updated_by
        self.append_row("id_sequences", new_row)

    # ============================================================
    # Append helpers
    # ============================================================
    def append_row(self, table: str, row: dict):
        ws = self.sh.worksheet(table)
        header = ws.row_values(1)
        values = [("" if row.get(col) is None else str(row.get(col))) for col in header]
        ws.append_row(values, value_input_option="USER_ENTERED")

    def append_audit_log(self, row: dict, sheet_name: str = "audit_log_test"):
        self.append_row(sheet_name, row)
