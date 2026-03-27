from __future__ import annotations

import pandas as pd

from shared.utils.common_helpers import _norm
from shared.services.spreadsheet_backend import (
    append_rows_by_header,
    bust_cache,
    get_header,
    get_table_versions,
    read_table,
    update_row_by_match,
    _replace_table_supabase,
    _clear_table_supabase,
)


def sheet_append(table: str, header: list[str], rows: list[list] | list[dict]):
    return append_rows_by_header(table, header, rows)


def sheet_bust_cache():
    return bust_cache()


def sheet_get_header(table: str) -> list[str]:
    return get_header(table)


def sheet_get_spreadsheet():
    return None


def sheet_get_versions(table_names) -> dict:
    return get_table_versions(table_names)


def sheet_read(table: str) -> pd.DataFrame:
    return read_table(table)


def sheet_read_many(table_names) -> dict[str, pd.DataFrame]:
    return {name: sheet_read(name) for name in table_names}


def sheet_update(table: str, key: str, value: str, updates: dict):
    return update_row_by_match(table, key, value, updates)


def sheet_replace_table(table: str, header: list[str], rows: list[list] | list[dict]):
    return _replace_table_supabase(table, header, rows)


def sheet_clear_keep_header(table: str):
    return _clear_table_supabase(table)


def sheet_read_row_maps(table: str):
    df = read_table(table)
    if df.empty:
        return [], []

    header = [_norm(x) for x in df.columns]
    row_maps = []
    for row_num, (_idx, row) in enumerate(df.iterrows(), start=2):
        row_maps.append((row_num, {col: row.get(col, "") for col in header}))
    return header, row_maps


def sheet_find_row_number(table: str, key_field: str, key_value: str):
    header, row_maps = sheet_read_row_maps(table)
    if not header:
        raise ValueError(f"{table} missing header")
    if key_field not in header:
        raise ValueError(f"{table} missing {key_field}")

    for row_num, row_dict in row_maps:
        if _norm(row_dict.get(key_field, "")) == _norm(key_value):
            return row_num, header, row_dict
    return None, header, None


def sheet_update_cell(table: str, row_num: int, col_num: int, value):
    header, row_maps = sheet_read_row_maps(table)
    if not header:
        raise ValueError(f"{table} missing header")
    idx = int(row_num) - 2
    col_idx = int(col_num) - 1
    if idx < 0 or idx >= len(row_maps):
        raise ValueError(f"{table} row {row_num} out of range")
    if col_idx < 0 or col_idx >= len(header):
        raise ValueError(f"{table} col {col_num} out of range")

    _row_num, row_dict = row_maps[idx]
    key_field = header[0]
    key_value = row_dict.get(key_field, "")
    return update_row_by_match(table, key_field, key_value, {header[col_idx]: value})


def sheet_update_range(table: str, start_row: int, values: list[list], start_col: int = 1, value_input_option: str = "USER_ENTERED"):
    if not values:
        return
    header, row_maps = sheet_read_row_maps(table)
    if not header:
        raise ValueError(f"{table} missing header")

    for offset, value_row in enumerate(values):
        idx = int(start_row) + offset - 2
        if idx < 0 or idx >= len(row_maps):
            raise ValueError(f"{table} row {start_row + offset} out of range")
        _row_num, row_dict = row_maps[idx]
        key_field = header[0]
        key_value = row_dict.get(key_field, "")
        updates = {}
        for i, cell in enumerate(value_row):
            col_idx = int(start_col) - 1 + i
            if 0 <= col_idx < len(header):
                updates[header[col_idx]] = cell
        if updates:
            update_row_by_match(table, key_field, key_value, updates)


def sheet_update_row_values(table: str, row_num: int, header: list[str], row_values: list, value_input_option: str = "USER_ENTERED"):
    if not header:
        raise ValueError(f"{table} missing header")
    normalized = list(row_values)
    normalized = normalized[:len(header)] + [""] * max(0, len(header) - len(normalized))
    sheet_update_range(table, int(row_num), [normalized[:len(header)]], start_col=1, value_input_option=value_input_option)


__all__ = [
    "sheet_append",
    "sheet_bust_cache",
    "sheet_get_header",
    "sheet_get_spreadsheet",
    "sheet_get_versions",
    "sheet_read",
    "sheet_read_many",
    "sheet_update",
    "sheet_replace_table",
    "sheet_clear_keep_header",
    "sheet_update_cell",
    "sheet_update_range",
    "sheet_read_row_maps",
    "sheet_find_row_number",
    "sheet_update_row_values",
]
