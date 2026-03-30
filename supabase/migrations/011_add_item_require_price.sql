-- =============================================================================
-- 011_add_item_require_price.sql
-- 建立時間: 2026-03-31
-- 說明: 新增 items.require_price 欄位。
--   DEFAULT true：所有現有品項行為不變。
--   設為 false 的品項：叫貨時跳過價格驗證，unit_price / amount 寫 0。
-- =============================================================================

ALTER TABLE public.items
    ADD COLUMN IF NOT EXISTS require_price BOOLEAN DEFAULT true;
