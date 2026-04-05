-- =============================================================================
-- 028_cleanup_perm_005.sql
-- 建立時間: 2026-04-06
-- 說明:
--   清理孤立 permission key PERM_005（manage_system）。
--   系統最高權限已由 PERM_017（system.manage）接管，
--   所有 code 均已改為檢查 system.manage，PERM_005 為無效殘留。
--
--   執行順序：先刪 role_permissions（FK 子表），再刪 permissions（父表）。
-- =============================================================================

DELETE FROM public.role_permissions WHERE permission_id = 'PERM_005';
DELETE FROM public.permissions       WHERE permission_id = 'PERM_005';
