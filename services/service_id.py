from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from oms_core import allocate_ids
from operations.logic.user_query import norm_text
from services.service_sheet import sheet_bust_cache, sheet_get_spreadsheet


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def allocate_ids_map(id_map: dict):
    return allocate_ids(id_map)


def allocate_user_id() -> str:
    try:
        return allocate_ids_map({"users": 1})["users"][0]
    except Exception:
        sh = sheet_get_spreadsheet()
        if sh is None:
            raise ValueError("Spreadsheet connection is not available")

        ws = sh.worksheet("id_sequences")
        values = ws.get_all_values()
        if not values or len(values) < 2:
            raise ValueError("id_sequences worksheet has no usable data")

        header = [norm_text(x) for x in values[0]]
        rows = values[1:]
        df = pd.DataFrame(rows, columns=header)
        required = ["key", "env", "prefix", "width", "next_value"]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Missing required column in id_sequences: {col}")

        hit = df[(df["key"].astype(str).str.strip() == "users") & (df["env"].astype(str).str.strip() == "prod")]
        if hit.empty:
            raise ValueError("Cannot find id_sequences row for users/prod")

        idx = hit.index[0]
        prefix = norm_text(df.at[idx, "prefix"])
        width = int(pd.to_numeric(df.at[idx, "width"], errors="coerce") or 0)
        next_value = int(pd.to_numeric(df.at[idx, "next_value"], errors="coerce") or 0)
        if not prefix or width <= 0 or next_value <= 0:
            raise ValueError("Invalid users sequence configuration")

        new_user_id = f"{prefix}{str(next_value).zfill(width)}"
        df.at[idx, "next_value"] = str(next_value + 1)
        if "updated_at" in df.columns:
            df.at[idx, "updated_at"] = _now_ts()
        if "updated_by" in df.columns:
            df.at[idx, "updated_by"] = str(st.session_state.get("login_user", "")).strip()

        out_values = [header] + df[header].fillna("").astype(str).values.tolist()
        ws.update(out_values)
        sheet_bust_cache()
        return new_user_id
