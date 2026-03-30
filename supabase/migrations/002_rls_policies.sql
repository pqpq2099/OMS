-- =============================================================================
-- 002_rls_policies.sql  —  Row Level Security Policies
-- 建立時間: 2026-03-30
-- 說明:
--   - 對所有業務表啟用 RLS
--   - service_role 使用 Supabase 內建繞過機制（不需額外 policy）
--   - anon 只可讀取參考資料表（units / brands / roles）
--   - 應用層後端應使用 SUPABASE_SERVICE_ROLE_KEY，不可用 anon key 寫入
--
-- 套用方式: supabase db push（或於 Supabase Dashboard > SQL Editor 執行）
-- 回滾方式: 見 rollback.md
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 啟用 RLS（所有業務表）
-- -----------------------------------------------------------------------------

ALTER TABLE public.items           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vendors         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stores          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brands          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.roles           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.units           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prices          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.unit_conversions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.item_specs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stocktakes      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stocktake_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.purchase_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.purchase_order_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.id_sequences    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.settings        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.line_groups     ENABLE ROW LEVEL SECURITY;

-- -----------------------------------------------------------------------------
-- anon 讀取 policy（參考資料表）
-- 讓前端可讀單位名稱、品牌、角色等 master data，無敏感性資訊
-- -----------------------------------------------------------------------------

-- units: anon 可 SELECT（用於中文單位顯示）
DROP POLICY IF EXISTS "anon_select_units" ON public.units;
CREATE POLICY "anon_select_units"
    ON public.units FOR SELECT
    TO anon
    USING (true);

-- brands: anon 可 SELECT
DROP POLICY IF EXISTS "anon_select_brands" ON public.brands;
CREATE POLICY "anon_select_brands"
    ON public.brands FOR SELECT
    TO anon
    USING (true);

-- roles: anon 可 SELECT（需顯示角色名稱）
DROP POLICY IF EXISTS "anon_select_roles" ON public.roles;
CREATE POLICY "anon_select_roles"
    ON public.roles FOR SELECT
    TO anon
    USING (true);

-- -----------------------------------------------------------------------------
-- 其他所有表：anon 無任何存取（RLS 啟用但無 policy = 全部拒絕）
-- service_role key 繞過 RLS，不需要額外 policy
-- -----------------------------------------------------------------------------

-- 說明：以下表啟用 RLS 後，anon 完全無法讀寫：
--   items / vendors / stores / users / prices / unit_conversions /
--   item_specs / stocktakes / stocktake_lines / purchase_orders /
--   purchase_order_lines / transactions / audit_logs /
--   id_sequences / settings / line_groups
--
-- 應用層必須使用 SUPABASE_SERVICE_ROLE_KEY（見 supabase_client.py）。

-- =============================================================================
-- 驗證查詢（可於 Dashboard 手動執行）
-- =============================================================================
-- SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';
-- 預期：全部 rowsecurity = true
--
-- SELECT * FROM pg_policies WHERE schemaname = 'public';
-- 預期：units / brands / roles 各有一條 anon SELECT policy
