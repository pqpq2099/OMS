from __future__ import annotations

from oms_core import _norm, _safe_float, read_table


def get_existing_order_maps(po_id: str) -> tuple[dict[str, float], dict[str, str]]:
    if not po_id:
        return {}, {}

    pol_df = read_table("purchase_order_lines")
    if pol_df.empty or "po_id" not in pol_df.columns:
        return {}, {}

    work = pol_df[pol_df["po_id"].astype(str).str.strip() == str(po_id).strip()].copy()

    qty_map = {}
    unit_map = {}
    for _, row in work.iterrows():
        item_id = _norm(row.get("item_id", ""))
        if not item_id:
            continue
        qty_map[item_id] = _safe_float(row.get("order_qty", row.get("qty", 0)))
        unit_map[item_id] = _norm(row.get("order_unit", row.get("unit_id", "")))
    return qty_map, unit_map
