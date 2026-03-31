from __future__ import annotations

import pandas as pd

from shared.utils.common_helpers import _norm, _now_ts, _safe_float
from shared.services.data_backend import append_rows_by_header, get_header, read_table, bust_cache
from shared.services.supabase_client import update_rows


def _make_id(prefix: str, width: int, n: int) -> str:
    return f"{prefix}{str(n).zfill(int(width))}"

def allocate_ids(request_counts: dict[str, int], env: str = "prod") -> dict[str, list[str]]:
    request_counts = {k: int(v) for k, v in request_counts.items() if int(v) > 0}
    result = {k: [] for k in request_counts.keys()}

    if not request_counts:
        return result

    df = read_table("id_sequences").copy()
    if df.empty:
        raise ValueError("Supabase 已連線，但 id_sequences 尚未初始化")

    required = ["key", "env", "prefix", "width", "next_value"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"id_sequences 缺少欄位：{col}")

    now = _now_ts()

    for key, cnt in request_counts.items():
        hit = df[
            (df["key"].astype(str).str.strip() == str(key).strip())
            & (df["env"].astype(str).str.strip() == str(env).strip())
        ]

        if hit.empty:
            raise ValueError(f"id_sequences 找不到 key={key}, env={env}")

        idx = hit.index[0]
        prefix = _norm(df.at[idx, "prefix"])
        width = int(_safe_float(df.at[idx, "width"], 0))
        next_value = int(_safe_float(df.at[idx, "next_value"], 0))

        if not prefix or width <= 0 or next_value <= 0:
            raise ValueError(f"id_sequences 設定錯誤：key={key}")

        ids = [_make_id(prefix, width, next_value + i) for i in range(cnt)]
        result[key] = ids

        df.at[idx, "next_value"] = str(next_value + cnt)
        if "updated_at" in df.columns:
            df.at[idx, "updated_at"] = now

        try:
            update_rows("id_sequences", {"key": str(key).strip(), "env": str(env).strip()}, {"next_value": str(next_value + cnt), "updated_at": now})
        except Exception:
            raise

    bust_cache("id_sequences")
    return result
