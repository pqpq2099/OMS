-- =============================================================================
-- 029_add_items_require_price_to_test.sql
-- 建立時間: 2026-04-06
-- 說明:
--   OMS_TEST（develop）的 items 表缺少 require_price 欄位。
--   OMS_V1（main）已有此欄（boolean, nullable, default true），為核心業務欄位，
--   控制採購價格是否必填。
--
--   本 migration 僅套用於 OMS_TEST（hikmpynwpqtbgqhsuyqd）。
--   OMS_V1 不需要，已存在。
-- =============================================================================

ALTER TABLE public.items
  ADD COLUMN IF NOT EXISTS require_price boolean DEFAULT true;
