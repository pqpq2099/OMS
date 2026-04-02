# ============================================================
# ORIVIA OMS
# 檔案：operations/logic/logic_stocktake_history.py
# 說明：盤點歷史查詢頁 — 邏輯層（read-only）
# 功能：載入 stocktakes + stocktake_lines + po_map + vendor_map
# ============================================================

from __future__ import annotations

from datetime import date

import pandas as pd

from shared.services.data_backend import read_table


# ----------------------------------------------------------
# 內部工具
# ----------------------------------------------------------

def _safe_str(val) -> str:
    """將 pandas 讀出的值轉為安全字串，清除 nan/None。"""
    s = str(val).strip()
    return "" if s in ("nan", "None", "NaN", "none") else s


def _build_vendor_map(vendors_df: pd.DataFrame) -> dict[str, str]:
    """建立 {vendor_id: display_name} 對照表。vendor_name_zh 優先。"""
    m: dict[str, str] = {}
    if vendors_df.empty or "vendor_id" not in vendors_df.columns:
        return m
    for _, row in vendors_df.iterrows():
        vid = _safe_str(row.get("vendor_id", ""))
        if not vid:
            continue
        name = (
            _safe_str(row.get("vendor_name_zh", ""))
            or _safe_str(row.get("vendor_name", ""))
            or vid
        )
        m[vid] = name
    return m


def _build_unit_map(units_df: pd.DataFrame) -> dict[str, str]:
    """建立 {unit_id: display_name} 對照表。unit_name_zh 優先。"""
    m: dict[str, str] = {}
    if units_df.empty or "unit_id" not in units_df.columns:
        return m
    for _, row in units_df.iterrows():
        uid = _safe_str(row.get("unit_id", ""))
        if not uid:
            continue
        name = (
            _safe_str(row.get("unit_name_zh", ""))
            or _safe_str(row.get("unit_name", ""))
            or uid
        )
        m[uid] = name
    return m


# ----------------------------------------------------------
# 公開函式
# ----------------------------------------------------------

def load_stocktake_history(
    store_id: str,
    filter_date: date,
    vendor_filter: str = "",
) -> tuple[
    pd.DataFrame,          # stk_df      — 篩選後的 stocktakes
    pd.DataFrame,          # stl_df      — 對應的 stocktake_lines（含 order_unit_display）
    dict[str, tuple],      # po_map      — {stocktake_id: (po_id, status)}
    dict[str, str],        # vendor_map  — {vendor_id: display_name}
    list[str],             # vendor_options — 本日所有出現的 vendor_id（不受 vendor_filter 影響）
]:
    """
    讀取盤點歷史資料（read-only）。

    vendor_options 永遠反映本日全部廠商（不受 vendor_filter 影響），
    供頁面建立廠商選單使用。stk_df / stl_df / po_map 依 vendor_filter 篩選。

    回傳順序：stk_df, stl_df, po_map, vendor_map, vendor_options
    """
    _empty: tuple = pd.DataFrame(), pd.DataFrame(), {}, {}, []

    # ── 1. 廠商對照表 ─────────────────────────────────────
    vendor_map = _build_vendor_map(read_table("vendors"))

    # ── 2. 載入 stocktakes ────────────────────────────────
    stk_raw = read_table("stocktakes")
    if stk_raw.empty:
        return pd.DataFrame(), pd.DataFrame(), {}, vendor_map, []

    stk_all = stk_raw.copy()

    # 依 store_id 過濾
    if store_id and "store_id" in stk_all.columns:
        stk_all = stk_all[
            stk_all["store_id"].astype(str).str.strip() == store_id
        ]

    # 依 stocktake_date 過濾（字串前綴比對相容 timestamp）
    if "stocktake_date" in stk_all.columns:
        date_str = str(filter_date)
        stk_all = stk_all[
            stk_all["stocktake_date"].astype(str).str.strip().str.startswith(date_str)
        ]

    if stk_all.empty:
        return pd.DataFrame(), pd.DataFrame(), {}, vendor_map, []

    # ── 3. 建立廠商選單（從本日全部盤點，不受 vendor_filter 影響）──
    vendor_options: list[str] = sorted(
        vid
        for vid in stk_all["vendor_id"].astype(str).str.strip().unique().tolist()
        if vid and vid not in ("nan", "None", "NaN", "")
    ) if "vendor_id" in stk_all.columns else []

    # ── 4. 套用廠商篩選 ───────────────────────────────────
    stk_df = stk_all.copy()
    if vendor_filter and vendor_filter not in ("", "全部"):
        if "vendor_id" in stk_df.columns:
            stk_df = stk_df[
                stk_df["vendor_id"].astype(str).str.strip() == vendor_filter
            ]

    if stk_df.empty:
        return pd.DataFrame(), pd.DataFrame(), {}, vendor_map, vendor_options

    stk_df = stk_df.reset_index(drop=True)
    stocktake_ids: set[str] = set(
        stk_df["stocktake_id"].astype(str).str.strip().tolist()
    )

    # ── 5. 載入 stocktake_lines ───────────────────────────
    stl_raw = read_table("stocktake_lines")
    stl_df: pd.DataFrame

    if not stl_raw.empty and "stocktake_id" in stl_raw.columns:
        stl_df = stl_raw[
            stl_raw["stocktake_id"].astype(str).str.strip().isin(stocktake_ids)
        ].copy().reset_index(drop=True)

        # 建立 order_unit_display 欄位（order_unit_id → 顯示名稱）
        unit_map = _build_unit_map(read_table("units"))
        if "order_unit_id" in stl_df.columns:
            stl_df["order_unit_display"] = stl_df["order_unit_id"].apply(
                lambda uid: unit_map.get(_safe_str(uid), _safe_str(uid))
            )
        else:
            stl_df["order_unit_display"] = ""
    else:
        stl_df = pd.DataFrame()

    # ── 6. 載入 purchase_orders → 建立 po_map ─────────────
    po_df = read_table("purchase_orders")
    po_map: dict[str, tuple[str, str]] = {}

    if not po_df.empty and "stocktake_id" in po_df.columns:
        po_filtered = po_df[
            po_df["stocktake_id"].astype(str).str.strip().isin(stocktake_ids)
        ]
        for _, row in po_filtered.iterrows():
            sid = _safe_str(row.get("stocktake_id", ""))
            pid = _safe_str(row.get("po_id", ""))
            status = _safe_str(row.get("status", ""))
            if sid:
                po_map[sid] = (pid, status)

    return stk_df, stl_df, po_map, vendor_map, vendor_options
