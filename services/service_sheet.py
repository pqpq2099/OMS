from oms_core import (
    append_rows_by_header,
    bust_cache,
    get_header,
    get_spreadsheet,
    read_table,
    update_row_by_match,
)


def sheet_append(table, header, rows):
    return append_rows_by_header(table, header, rows)


def sheet_get_header(table):
    return get_header(table)


def sheet_read(table):
    return read_table(table)


def sheet_update(table, key, value, updates):
    return update_row_by_match(table, key, value, updates)


def sheet_get_spreadsheet():
    return get_spreadsheet()


def sheet_bust_cache():
    return bust_cache()
