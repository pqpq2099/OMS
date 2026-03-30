-- =============================================================================
-- 006_recreate_partial_unique_indexes.sql
-- 建立時間: 2026-03-30
-- 說明: 確保 stocktake_lines / purchase_order_lines 的 partial unique index 存在。
--       003 已建立，此為冪等補強（IF NOT EXISTS）。
-- =============================================================================

CREATE UNIQUE INDEX IF NOT EXISTS uidx_stocktake_lines_stl_id
    ON public.stocktake_lines (stocktake_line_id)
    WHERE stocktake_line_id IS NOT NULL AND stocktake_line_id <> '';

CREATE UNIQUE INDEX IF NOT EXISTS uidx_purchase_order_lines_pol_id
    ON public.purchase_order_lines (po_line_id)
    WHERE po_line_id IS NOT NULL AND po_line_id <> '';
