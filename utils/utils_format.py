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


def _fmt_qty_with_unit(qty: float, unit: str) -> str:
    qty_value = 0.0
    try:
        qty_value = float(qty)
    except Exception:
        qty_value = 0.0

    unit_text = str(unit or "").strip()
    if unit_text:
        return f"{qty_value:g}{unit_text}"
    return f"{qty_value:g}"
