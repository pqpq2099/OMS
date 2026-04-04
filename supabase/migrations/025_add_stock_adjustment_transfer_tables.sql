-- =============================================================================
-- 025_add_stock_adjustment_transfer_tables.sql
-- 建立時間: 2026-04-05
-- 說明:
--   新增兩個功能所需的資料表：
--     1. stock_adjustments   — 庫存調整審計記錄（store_manager+ 可執行）
--     2. stock_transfers      — 調貨 header（leader+ 可執行）
--     3. stock_transfer_lines — 調貨明細
--
--   每張表均啟用 RLS + service_role_bypass policy（與其他表一致）
--   本 migration 安全可重複執行（IF NOT EXISTS）。
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. stock_adjustments（庫存調整審計表）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.stock_adjustments (
    adjustment_id      TEXT PRIMARY KEY,
    store_id           TEXT NOT NULL,
    adjustment_date    DATE NOT NULL,
    item_id            TEXT NOT NULL,
    item_name          TEXT,
    vendor_id          TEXT,
    before_base_qty    NUMERIC,
    delta_base_qty     NUMERIC NOT NULL,
    after_base_qty     NUMERIC,
    base_unit          TEXT,
    display_unit       TEXT,
    before_display_qty NUMERIC,
    delta_display_qty  NUMERIC,
    after_display_qty  NUMERIC,
    note               TEXT,
    created_by         TEXT NOT NULL,
    created_at         TIMESTAMP DEFAULT NOW()
);

ALTER TABLE public.stock_adjustments ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'stock_adjustments' AND policyname = 'service_role_bypass'
    ) THEN
        CREATE POLICY service_role_bypass ON public.stock_adjustments
            TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 2. stock_transfers（調貨 header）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.stock_transfers (
    transfer_id    TEXT PRIMARY KEY,
    batch_id       TEXT,
    transfer_date  DATE NOT NULL,
    from_store_id  TEXT NOT NULL,
    to_store_id    TEXT NOT NULL,
    status         TEXT DEFAULT 'confirmed',
    note           TEXT,
    created_by     TEXT NOT NULL,
    created_at     TIMESTAMP DEFAULT NOW()
);

ALTER TABLE public.stock_transfers ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'stock_transfers' AND policyname = 'service_role_bypass'
    ) THEN
        CREATE POLICY service_role_bypass ON public.stock_transfers
            TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 3. stock_transfer_lines（調貨明細）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.stock_transfer_lines (
    transfer_line_id TEXT PRIMARY KEY,
    transfer_id      TEXT NOT NULL,
    from_store_id    TEXT NOT NULL,
    to_store_id      TEXT NOT NULL,
    vendor_id        TEXT,
    item_id          TEXT NOT NULL,
    item_name        TEXT,
    base_qty         NUMERIC NOT NULL,
    base_unit        TEXT,
    display_qty      NUMERIC,
    display_unit     TEXT,
    note             TEXT,
    created_at       TIMESTAMP DEFAULT NOW()
);

ALTER TABLE public.stock_transfer_lines ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'stock_transfer_lines' AND policyname = 'service_role_bypass'
    ) THEN
        CREATE POLICY service_role_bypass ON public.stock_transfer_lines
            TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;
