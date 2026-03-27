from functools import lru_cache

from shared.services.spreadsheet_backend import read_table
from shared.utils.common_helpers import _norm


@lru_cache(maxsize=1)
def _unit_display_map() -> dict[str, str]:
    try:
        units_df = read_table("units")
    except Exception:
        return {}

    if units_df is None or units_df.empty or "unit_id" not in units_df.columns:
        return {}

    unit_map: dict[str, str] = {}
    for _, row in units_df.iterrows():
        unit_id = _norm(row.get("unit_id"))
        if not unit_id:
            continue
        label = _norm(row.get("unit_name_zh")) or _norm(row.get("unit_name")) or unit_id
        unit_map[unit_id] = label
    return unit_map


def unit_label(unit_value: str) -> str:
    text = _norm(unit_value)
    if not text:
        return ""
    return _unit_display_map().get(text, text)


def clear_unit_label_cache():
    _unit_display_map.cache_clear()


def _fmt_qty_with_unit(qty: float, unit: str) -> str:
    qty_value = 0.0
    try:
        qty_value = float(qty)
    except Exception:
        qty_value = 0.0

    unit_text = unit_label(unit)
    if unit_text:
        return f"{qty_value:g}{unit_text}"
    return f"{qty_value:g}"
