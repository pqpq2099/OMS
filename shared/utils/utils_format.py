# ============================================================
# ORIVIA OMS
# 檔案：utils/utils_format.py
# 說明：格式工具模組
# 功能：處理顯示格式、日期、數字與文字整理。
# 注意：偏向畫面顯示與資料格式化。
# ============================================================

"""
工具模組：格式整理。
例如文字、欄位、顯示格式等小工具。
"""

from functools import lru_cache

from shared.services.spreadsheet_backend import read_table


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
        unit_id = str(row.get("unit_id", "")).strip()
        if not unit_id:
            continue
        label = (
            str(row.get("unit_name_zh", "")).strip()
            or str(row.get("unit_name", "")).strip()
            or unit_id
        )
        unit_map[unit_id] = label
    return unit_map


def unit_label(unit_value: str) -> str:
    text = str(unit_value or "").strip()
    if not text:
        return ""
    return _unit_display_map().get(text, text)


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
