from __future__ import annotations

import pandas as pd

from shared.utils.common_helpers import _norm
from shared.services.spreadsheet_backend import (
    append_rows_by_header,
    bust_cache,
    get_header,
    get_spreadsheet,
    get_table_versions,
    read_table,
    update_row_by_match,
)


def _sheet_col_to_letter(n: int) -> str:
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def sheet_append(table: str, header: list[str], rows: list[list]):
    return append_rows_by_header(table, header, rows)


def sheet_bust_cache():
    return bust_cache()


def sheet_get_header(table: str) -> list[str]:
    return get_header(table)


def sheet_get_spreadsheet():
    return get_spreadsheet()


def sheet_get_versions(table_names) -> dict:
    return get_table_versions(table_names)


def sheet_read(table: str) -> pd.DataFrame:
    return read_table(table)


def sheet_read_many(table_names) -> dict[str, pd.DataFrame]:
    return {name: sheet_read(name) for name in table_names}


def sheet_update(table: str, key: str, value: str, updates: dict):
    return update_row_by_match(table, key, value, updates)


def sheet_replace_table(table: str, header: list[str], rows: list[list] | list[dict]):
    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet(table)
    normalized_rows = []
    for row in rows:
        if isinstance(row, dict):
            normalized_rows.append([row.get(col, "") for col in header])
        else:
            values = list(row)
            values = values[:len(header)] + [""] * max(0, len(header) - len(values))
            normalized_rows.append(values[:len(header)])

    ws.clear()
    ws.update([header] + normalized_rows)
    bust_cache(table)


def sheet_clear_keep_header(table: str):
    header = get_header(table)
    sheet_replace_table(table, header, [])


def sheet_update_cell(table: str, row_num: int, col_num: int, value):
    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")
    ws = sh.worksheet(table)
    ws.update_cell(int(row_num), int(col_num), value)
    bust_cache(table)


def sheet_update_range(table: str, start_row: int, values: list[list], start_col: int = 1, value_input_option: str = "USER_ENTERED"):
    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")
    ws = sh.worksheet(table)
    if not values:
        return
    end_row = start_row + len(values) - 1
    end_col = start_col + len(values[0]) - 1
    range_ref = f"{_sheet_col_to_letter(start_col)}{start_row}:{_sheet_col_to_letter(end_col)}{end_row}"
    ws.update(range_ref, values, value_input_option=value_input_option)
    bust_cache(table)


def sheet_read_row_maps(table: str):
    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet(table)
    values = ws.get_all_values()
    if not values:
        return [], []

    header = [_norm(x) for x in values[0]]
    row_maps = []
    for row_num, row in enumerate(values[1:], start=2):
        row_values = list(row)
        row_values = row_values[:len(header)] + [""] * max(0, len(header) - len(row_values))
        row_maps.append((row_num, {col: row_values[idx] for idx, col in enumerate(header)}))
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
