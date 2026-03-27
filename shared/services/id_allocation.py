from __future__ import annotations

import pandas as pd

from shared.utils.common_helpers import _norm, _now_ts, _safe_float
from shared.services.spreadsheet_backend import get_header, read_table, update_row_by_match, bust_cache


def _make_id(prefix: str, width: int, n: int) -> str:
    return f"{prefix}{str(n).zfill(int(width))}"


def allocate_ids(request_counts: dict[str, int], env: str = "prod") -> dict[str, list[str]]:
    request_counts = {k: int(v) for k, v in request_counts.items() if int(v) > 0}
    result = {k: [] for k in request_counts.keys()}

    if not request_counts:
        return result

    df = read_table("id_sequences").copy()
    if df.empty:
        raise ValueError("id_sequences 為空")

    required = ["key", "env", "prefix", "width", "next_value"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"id_sequences 缺少欄位：{col}")

    now = _now_ts()

    for key, cnt in request_counts.items():
        hit = df[(df["key"].astype(str).str.strip() == str(key).strip()) & (df["env"].astype(str).str.strip() == str(env).strip())]
        if hit.empty:
            raise ValueError(f"id_sequences 找不到 key={key}, env={env}")

        row = hit.iloc[0]
        seq_key = _norm(row.get("key"))
        prefix = _norm(row.get("prefix"))
        width = int(_safe_float(row.get("width"), 0))
        next_value = int(_safe_float(row.get("next_value"), 0))

        if not prefix or width <= 0 or next_value <= 0:
            raise ValueError(f"id_sequences 設定錯誤：key={key}")

        ids = [_make_id(prefix, width, next_value + i) for i in range(cnt)]
        result[key] = ids

        updates = {"next_value": str(next_value + cnt)}
        if "updated_at" in df.columns:
            updates["updated_at"] = now
        update_row_by_match("id_sequences", "key", seq_key, updates)

    bust_cache("id_sequences")
    return result
