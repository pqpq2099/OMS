-- =============================================================================
-- 008_add_po_stocktake_link.sql  —  purchase_orders.stocktake_id 正式關聯
-- 建立時間: 2026-03-31
-- 說明:
--   新增 purchase_orders.stocktake_id 欄位，建立與 stocktakes 的正式 FK 關聯。
--   - NULLABLE：不破壞既有 49 筆歷史資料（保留為 NULL）
--   - FK：確保新寫入的 stocktake_id 必須存在於 stocktakes
--   - Index：加速 JOIN / GROUP BY 查詢
-- =============================================================================

-- 1. 新增欄位（idempotent）
ALTER TABLE public.purchase_orders
    ADD COLUMN IF NOT EXISTS stocktake_id TEXT;

-- 2. FK constraint（先確認不存在再加，避免重複執行報錯）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'purchase_orders_stocktake_id_fkey'
          AND conrelid = 'public.purchase_orders'::regclass
    ) THEN
        ALTER TABLE public.purchase_orders
            ADD CONSTRAINT purchase_orders_stocktake_id_fkey
            FOREIGN KEY (stocktake_id)
            REFERENCES public.stocktakes(stocktake_id);
    END IF;
END;
$$;

-- 3. Index（加速 JOIN / WHERE stocktake_id = ...）
CREATE INDEX IF NOT EXISTS idx_purchase_orders_stocktake_id
    ON public.purchase_orders (stocktake_id);
