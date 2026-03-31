from __future__ import annotations

import pandas as pd
import streamlit as st

from operations.logic.order_errors import SystemProcessError
from shared.services.service_id import allocate_many_ids
from shared.services.service_order_core import norm, now_ts
from shared.services.data_backend import (
    append_rows_by_header as sheet_append,
    find_row_number as sheet_find_row_number,
    get_header as sheet_get_header,
    read_row_maps as sheet_read_row_maps,
    update_row_values as sheet_update_row_values,
)


def normalize_compare_value(value):
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
        old_v = normalize_compare_value(old_map.get(col, ""))
        new_v = normalize_compare_value(new_map.get(col, ""))
        if old_v != new_v:
            return False
    return True



def _update_row_by_id(sheet_name: str, id_field: str, entity_id: str, updates: dict):
    try:
        target_row_num, header, current = sheet_find_row_number(sheet_name, id_field, entity_id)
    except Exception as exc:
        raise SystemProcessError(str(exc)) from exc

    if target_row_num is None or current is None:
        raise SystemProcessError(f"{sheet_name} row not found: {entity_id}")

    candidate = dict(current)
    for key, value in updates.items():
        if key in candidate:
            candidate[key] = "" if value is None else value

    compare_ignore_fields = {"updated_at", "updated_by", "created_at", "created_by"}
    if _rows_equal_for_compare(current, candidate, header, compare_ignore_fields):
        return False

    sheet_update_row_values(sheet_name, target_row_num, header, [candidate.get(col, "") for col in header])
    return True



def _write_audit_log(action: str, table_name: str, entity_id: str, note: str, before_json: str = "{}", after_json: str = "{}"):
    try:
        header = sheet_get_header("audit_logs")
    except Exception:
        return

    if not header:
        return

    now = now_ts()
    login_user_id = norm(st.session_state.get("login_user_id", "")) or "SYSTEM"
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
    try:
        header, row_maps = sheet_read_row_maps(sheet_name)
    except Exception as exc:
        raise SystemProcessError(str(exc)) from exc

    if not header:
        raise SystemProcessError(f"{sheet_name} is empty")

    existing_by_item = {}
    for row_num, row_dict in row_maps:
        if norm(row_dict.get(parent_field, "")) != norm(parent_id):
            continue
        item_id = norm(row_dict.get("item_id", ""))
        if item_id:
            existing_by_item[item_id] = (row_num, row_dict)

    add_rows = []
    new_id_list = []
    has_changed = False

    need_new = [r for r in item_rows if norm(r.get("item_id", "")) not in existing_by_item]
    if need_new:
        new_id_list = allocate_many_ids(allocate_key, len(need_new))

    new_idx = 0
    compare_ignore_fields = {"updated_at", "updated_by", "created_at", "created_by"}

    for item_row in item_rows:
        item_id = norm(item_row.get("item_id", ""))
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

            sheet_update_row_values(sheet_name, row_num, header, [candidate.get(col, "") for col in header])
            has_changed = True
        else:
            row_dict = {c: "" for c in header}
            if line_id_field in row_dict and new_idx < len(new_id_list):
                row_dict[line_id_field] = new_id_list[new_idx]
                new_idx += 1
            for key, value in item_row.items():
                if key in row_dict:
                    if key == line_id_field:  # 不可覆蓋已分配的 line id
                        continue
                    row_dict[key] = "" if value is None else value
            add_rows.append(row_dict)

    if add_rows:
        sheet_append(sheet_name, header, add_rows)
        has_changed = True

    return has_changed
