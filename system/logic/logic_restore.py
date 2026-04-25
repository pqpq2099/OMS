from __future__ import annotations

# ============================================================
# ORIVIA OMS
# 檔案：system/logic/logic_restore.py
# 說明：從備份 Excel 還原歷史交易紀錄
# ============================================================

from typing import Any

import io
import math

import pandas as pd

from shared.services.supabase_client import upsert_rows
from shared.services.data_backend import bust_cache
from shared.services.table_contract import TABLE_CONTRACT

# ── 每張表的 PK 對照（TABLE_CONTRACT 有的用 CONTRACT，沒有的補齊） ──
_TABLE_PK: dict[str, str] = {
    "stocktakes":           "stocktake_id",
    "stocktake_lines":      "stocktake_line_id",
    "purchase_orders":      "po_id",
    "purchase_order_lines": "po_line_id",
    "transactions":         "txn_id",
    "stock_adjustments":    "adjustment_id",
    "stock_transfers":      "transfer_id",
    "stock_transfer_lines": "transfer_line_id",
    "audit_logs":           "audit_id",
    "items":                "item_id",
    "item_specs":           "spec_id",
    "brands":               "brand_id",
    "units":                "unit_id",
    "unit_conversions":     "conversion_id",
    "prices":               "price_id",
    "stores":               "store_id",
    "vendors":              "vendor_id",
}


def _get_pk(table_name: str) -> str | None:
    """取得表的 PK 欄位名稱。優先用 TABLE_CONTRACT，再用本地對照。"""
    contract = TABLE_CONTRACT.get(table_name)
    if contract and contract.get("primary_key"):
        return contract["primary_key"]
    return _TABLE_PK.get(table_name)


def preview_restore(
    file_bytes: bytes,
    backup_tables: list[tuple[str, str, str]],
) -> list[dict[str, Any]]:
    """
    預覽備份檔內容。回傳每張表的狀態清單。

    回傳格式：
    [
        {"table": "items", "sheet": "品項", "status": "ok", "count": 32, "msg": ""},
        {"table": "xxx",   "sheet": "xxx",  "status": "skip", "count": 0, "msg": "找不到此分頁"},
        ...
    ]
    """
    try:
        all_sheets = pd.ExcelFile(io.BytesIO(file_bytes)).sheet_names
    except Exception as e:
        return [{"table": "", "sheet": "", "status": "error", "count": 0,
                 "msg": f"無法讀取 Excel 檔案：{e}"}]

    results: list[dict[str, Any]] = []
    for table_name, sheet_name, _cat in backup_tables:
        if sheet_name not in all_sheets:
            results.append({
                "table": table_name, "sheet": sheet_name,
                "status": "skip", "count": 0, "msg": "找不到此分頁",
            })
            continue

        try:
            df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name)
        except Exception as e:
            results.append({
                "table": table_name, "sheet": sheet_name,
                "status": "error", "count": 0, "msg": f"讀取失敗：{e}",
            })
            continue

        if df.empty:
            results.append({
                "table": table_name, "sheet": sheet_name,
                "status": "skip", "count": 0, "msg": "無資料（空表）",
            })
            continue

        pk = _get_pk(table_name)
        if not pk:
            results.append({
                "table": table_name, "sheet": sheet_name,
                "status": "error", "count": len(df), "msg": "找不到 PK 定義",
            })
            continue

        if pk not in df.columns:
            results.append({
                "table": table_name, "sheet": sheet_name,
                "status": "error", "count": len(df),
                "msg": f"缺少 PK 欄位：{pk}",
            })
            continue

        results.append({
            "table": table_name, "sheet": sheet_name,
            "status": "ok", "count": len(df), "msg": "",
        })

    return results


def execute_restore(
    file_bytes: bytes,
    backup_tables: list[tuple[str, str, str]],
) -> list[dict[str, Any]]:
    """
    執行還原。逐表 upsert，跳過無法處理的表。

    回傳格式同 preview_restore，但 status 增加 "done" / "fail"。
    """
    try:
        all_sheets = pd.ExcelFile(io.BytesIO(file_bytes)).sheet_names
    except Exception as e:
        return [{"table": "", "sheet": "", "status": "fail", "count": 0,
                 "msg": f"無法讀取 Excel 檔案：{e}"}]

    results: list[dict[str, Any]] = []
    for table_name, sheet_name, _cat in backup_tables:
        if sheet_name not in all_sheets:
            results.append({
                "table": table_name, "sheet": sheet_name,
                "status": "skip", "count": 0, "msg": "找不到此分頁",
            })
            continue

        try:
            df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name)
        except Exception:
            results.append({
                "table": table_name, "sheet": sheet_name,
                "status": "skip", "count": 0, "msg": "讀取失敗",
            })
            continue

        if df.empty:
            results.append({
                "table": table_name, "sheet": sheet_name,
                "status": "skip", "count": 0, "msg": "無資料",
            })
            continue

        pk = _get_pk(table_name)
        if not pk or pk not in df.columns:
            results.append({
                "table": table_name, "sheet": sheet_name,
                "status": "skip", "count": len(df),
                "msg": f"缺少 PK（{pk}），跳過",
            })
            continue

        # 清理 NaN / inf → None（Supabase 接受 null，但不接受 NaN/inf）
        rows = df.to_dict(orient="records")
        for row in rows:
            for k, v in row.items():
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    row[k] = None

        try:
            upsert_rows(table_name, rows, on_conflict=pk)
            bust_cache(table_name)
            results.append({
                "table": table_name, "sheet": sheet_name,
                "status": "done", "count": len(rows), "msg": "",
            })
        except Exception as e:
            results.append({
                "table": table_name, "sheet": sheet_name,
                "status": "fail", "count": len(rows), "msg": str(e),
            })

    return results
