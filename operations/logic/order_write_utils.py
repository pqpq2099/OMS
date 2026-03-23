from __future__ import annotations

import pandas as pd
import streamlit as st

from oms_core import _norm, _now_ts
from operations.logic.order_errors import SystemProcessError
from services.service_id import allocate_ids_map
from services.service_sheet import sheet_append, sheet_get_header, sheet_get_spreadsheet


def _sheet_col_to_letter(n: int) -> str:
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result



def _normalize_compare_value(value):
    if value is None:
        return ""

    text = str(value).strip()
    if text == "":
        return ""

    try:
        num = float(text)
        if num.is_integer():
            return str(int(num))
        return str(num)
    except Exception:
        return text


def _rows_equal_for_compare(old_map: dict, new_map: dict, header: list[str], ignore_fields: set[str] | None = None) -> bool:
    ignore_fields = ignore_fields or set()
    for col in header:
        if col in ignore_fields:
            continue
        old_v = _normalize_compare_value(old_map.get(col, ""))
        new_v = _normalize_compare_value(new_map.get(col, ""))
        if old_v != new_v:
            return False
    return True


def _update_row_by_id(sheet_name: str, id_field: str, entity_id: str, updates: dict):
    sh = sheet_get_spreadsheet()
    if sh is None:
        raise SystemProcessError("Spreadsheet not available")

    ws = sh.worksheet(sheet_name)
    header = [_norm(x) for x in ws.row_values(1)]
    if not header:
        raise SystemProcessError(f"{sheet_name} missing header")

    if id_field not in header:
        raise SystemProcessError(f"{sheet_name} missing {id_field}")

    values = ws.get_all_values()
    if not values:
        raise SystemProcessError(f"{sheet_name} is empty")

    id_idx = header.index(id_field)
    target_row_num = None
    for row_num, row in enumerate(values[1:], start=2):
        cell = row[id_idx] if id_idx < len(row) else ""
        if _norm(cell) == _norm(entity_id):
            target_row_num = row_num
            break

    if target_row_num is None:
        raise SystemProcessError(f"{sheet_name} row not found: {entity_id}")

    row_values = ws.row_values(target_row_num)
    if len(row_values) < len(header):
        row_values = row_values + [""] * (len(header) - len(row_values))
    else:
        row_values = row_values[:len(header)]

    current = {col: row_values[idx] for idx, col in enumerate(header)}
    candidate = dict(current)
    for key, value in updates.items():
        if key in candidate:
            candidate[key] = "" if value is None else value

    compare_ignore_fields = {"updated_at", "updated_by", "created_at", "created_by"}
    if _rows_equal_for_compare(current, candidate, header, compare_ignore_fields):
        return False

    new_row = [candidate.get(col, "") for col in header]
    end_col = _sheet_col_to_letter(len(header))
    ws.update(
        f"A{target_row_num}:{end_col}{target_row_num}",
        [new_row],
        value_input_option="USER_ENTERED",
    )
    return True


def _write_audit_log(action: str, table_name: str, entity_id: str, note: str, before_json: str = "{}", after_json: str = "{}"):
    try:
        header = sheet_get_header("audit_logs")
    except Exception:
        return

    if not header:
        return

    now = _now_ts()
    login_user_id = _norm(st.session_state.get("login_user_id", "")) or "SYSTEM"
    audit_id = f"AUDIT_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S%f')}"
    row = {c: "" for c in header}
    defaults = {
        "audit_id": audit_id,
        "ts": now,
        "user_id": login_user_id,
        "action": action,
        "table_name": table_name,
        "entity_id": entity_id,
        "before_json": before_json,
        "after_json": after_json,
        "note": note,
    }
    for k, v in defaults.items():
        if k in row:
            row[k] = v
    sheet_append("audit_logs", header, [row])


def _upsert_detail_rows_by_parent(
    sheet_name: str,
    parent_field: str,
    parent_id: str,
    line_id_field: str,
    item_rows: list[dict],
    allocate_key: str,
):
    sh = sheet_get_spreadsheet()
    if sh is None:
        raise SystemProcessError("Spreadsheet not available")

    ws = sh.worksheet(sheet_name)
    header = [_norm(x) for x in ws.row_values(1)]
    values = ws.get_all_values()
    if not values:
        raise SystemProcessError(f"{sheet_name} is empty")

    row_maps = []
    for row_num, row in enumerate(values[1:], start=2):
        row_values = list(row) + [""] * (len(header) - len(row))
        row_values = row_values[:len(header)]
        row_maps.append((row_num, {col: row_values[idx] for idx, col in enumerate(header)}))

    existing_by_item = {}
    for row_num, row_dict in row_maps:
        if _norm(row_dict.get(parent_field, "")) != _norm(parent_id):
            continue
        item_id = _norm(row_dict.get("item_id", ""))
        if item_id:
            existing_by_item[item_id] = (row_num, row_dict)

    add_rows = []
    new_id_list = []
    has_changed = False

    need_new = [r for r in item_rows if _norm(r.get("item_id", "")) not in existing_by_item]
    if need_new:
        allocated = allocate_ids_map({allocate_key: len(need_new)})
        new_id_list = allocated.get(allocate_key, [])

    new_idx = 0
    compare_ignore_fields = {"updated_at", "updated_by", "created_at", "created_by"}

    for item_row in item_rows:
        item_id = _norm(item_row.get("item_id", ""))
        if not item_id:
            continue

        if item_id in existing_by_item:
            row_num, row_dict = existing_by_item[item_id]
            current = dict(row_dict)
            candidate = dict(row_dict)
            for key, value in item_row.items():
                if key not in candidate:
                    continue
                if key in {"created_at", "created_by"}:
                    continue
                candidate[key] = "" if value is None else value

            if _rows_equal_for_compare(current, candidate, header, compare_ignore_fields):
                continue

            end_col = _sheet_col_to_letter(len(header))
            ws.update(
                f"A{row_num}:{end_col}{row_num}",
                [[candidate.get(col, "") for col in header]],
                value_input_option="USER_ENTERED",
            )
            has_changed = True
        else:
            row_dict = {c: "" for c in header}
            if line_id_field in row_dict and new_idx < len(new_id_list):
                row_dict[line_id_field] = new_id_list[new_idx]
                new_idx += 1
            for key, value in item_row.items():
                if key in row_dict:
                    row_dict[key] = "" if value is None else value
            add_rows.append(row_dict)

    if add_rows:
        sheet_append(sheet_name, header, add_rows)
        has_changed = True

    return has_changed
