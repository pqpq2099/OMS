"""
ID 產生器
從 id_sequences 表取得下一個 ID
"""

from __future__ import annotations

import pandas as pd
from oms_core import read_table, overwrite_table


def allocate_ids(key: str, count: int = 1):

    seq = read_table("id_sequences")

    row = seq[seq["key"] == key]

    if row.empty:
        raise ValueError(f"id_sequences 找不到 key={key}")

    idx = row.index[0]

    next_value = int(row.iloc[0]["next_value"])

    ids = []

    for i in range(count):
        ids.append(next_value + i)

    seq.loc[idx, "next_value"] = next_value + count

    overwrite_table("id_sequences", seq)

    return ids
