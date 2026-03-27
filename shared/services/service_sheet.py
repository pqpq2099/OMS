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
from shared.services.supabase_client import delete_rows, insert_rows, update_rows


def _sheet_col_to_letter(n: int) -> str:
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result




_PRIMARY_KEY_MAP = {
    "vendors": "vendor_id",
    "units": "unit_id",
    "items": "item_id",
    "prices": "price_id",
    "unit_conversions": "conversion_id",
    "purchase_orders": "po_id",
    "purchase_order_lines": "po_line_id",
    "stocktakes": "stocktake_id",
    "stocktake_lines": "stocktake_line_id",
    "transactions": "txn_id",
    "audit_logs": "audit_id",
    "users": "user_id",
    "stores": "store_id",
    "settings": "key",
    "id_sequences": "key",
}


def _primary_key_for_table(table: str, header: list[str] | None = None) -> str | None:
    key = _PRIMARY_KEY_MAP.get(_norm(table))
    if key:
        return key
    header = header or []
    for col in header:
        if str(col).strip().endswith("_id"):
            return str(col).strip()
    return None


def _rows_to_dicts(header: list[str], rows: list[list] | list[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        if isinstance(row, dict):
            out.append({col: row.get(col, "") for col in header})
        else:
            values = list(row)
            values = values[:len(header)] + [""] * max(0, len(header) - len(values))
            out.append({col: values[idx] for idx, col in enumerate(header)})
    return out

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
    records = _rows_to_dicts(header, rows)
    pk = _primary_key_for_table(table, header)

    try:
        if pk:
            existing = sheet_read(table)
            if existing is not None and not existing.empty and pk in existing.columns:
                for _, r in existing.iterrows():
                    key_val = _norm(r.get(pk))
                    if key_val:
                        delete_rows(table, {pk: key_val})
            if records:
                insert_rows(table, records)
            bust_cache(table)
            return
    except Exception:
        pass

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
    header = sheet_get_header(table)
    if not header:
        raise ValueError(f"{table} missing header")
    if int(col_num) <= 0 or int(col_num) > len(header):
        raise ValueError(f"{table} invalid col_num={col_num}")

    df = sheet_read(table)
    idx = int(row_num) - 2
    if df is None or df.empty or idx < 0 or idx >= len(df):
        raise ValueError(f"{table} invalid row_num={row_num}")

    pk = _primary_key_for_table(table, list(df.columns))
    if not pk or pk not in df.columns:
        raise ValueError(f"{table} missing primary key for update")

    row = df.iloc[idx].to_dict()
    row[header[int(col_num) - 1]] = value
    key_val = _norm(row.get(pk))
    update_rows(table, {pk: key_val}, row)
    bust_cache(table)


def sheet_update_range(table: str, start_row: int, values: list[list], start_col: int = 1, value_input_option: str = "USER_ENTERED"):
    header = sheet_get_header(table)
    if not header or not values:
        return

    df = sheet_read(table)
    pk = _primary_key_for_table(table, list(df.columns) if df is not None else header)
    if df is None or df.empty or not pk or pk not in df.columns:
        raise ValueError(f"{table} cannot update range")

    for offset, row_values in enumerate(values):
        idx = int(start_row) - 2 + offset
        if idx < 0 or idx >= len(df):
            continue
        row = df.iloc[idx].to_dict()
        for i, value in enumerate(row_values):
            col_idx = int(start_col) - 1 + i
            if 0 <= col_idx < len(header):
                row[header[col_idx]] = value
        key_val = _norm(row.get(pk))
        update_rows(table, {pk: key_val}, row)

    bust_cache(table)


def sheet_read_row_maps(table: str):
    df = sheet_read(table).copy()
    if df is None or df.empty:
        return [], []

    header = [_norm(x) for x in list(df.columns)]
    row_maps = []
    for row_num, (_, row) in enumerate(df.iterrows(), start=2):
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


def sheet_update_row_values(table: str, row_num: int, header: list[str], row_values: list, value_input_option: str = "USER_ENTERED"):
    if not header:
        raise ValueError(f"{table} missing header")

    normalized = list(row_values)
    normalized = normalized[:len(header)] + [""] * max(0, len(header) - len(normalized))

    df = sheet_read(table)
    idx = int(row_num) - 2
    if df is None or df.empty or idx < 0 or idx >= len(df):
        raise ValueError(f"{table} invalid row_num={row_num}")

    pk = _primary_key_for_table(table, list(df.columns))
    if not pk or pk not in df.columns:
        raise ValueError(f"{table} missing primary key for row update")

    row = df.iloc[idx].to_dict()
    for i, col in enumerate(header):
        row[col] = normalized[i]

    key_val = _norm(row.get(pk))
    update_rows(table, {pk: key_val}, row)
    bust_cache(table)


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
