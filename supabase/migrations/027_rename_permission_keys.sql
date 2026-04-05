-- =============================================================================
-- 027_rename_permission_keys.sql
-- 建立時間: 2026-04-06
-- 說明:
--   將舊 permission_key 統一改為 3-part {domain}.{resource}.{action} 格式。
--   只更新 permission_key，不異動 role_permissions（PERM_ID 不變）。
--
--   PERM_005（manage_system）跳過：PERM_017 已有 system.manage，
--   owner 已持有 PERM_017，code 已改為檢查 system.manage。
--
--   role_permissions 無需調整，PERM_ID 對應角色已正確。
-- =============================================================================

UPDATE public.permissions SET permission_key = 'data.purchase.manage'     WHERE permission_id = 'PERM_001';
UPDATE public.permissions SET permission_key = 'system.store.manage'      WHERE permission_id = 'PERM_002';
UPDATE public.permissions SET permission_key = 'user.account.manage'      WHERE permission_id = 'PERM_003';
UPDATE public.permissions SET permission_key = 'system.info.view'         WHERE permission_id = 'PERM_004';
-- PERM_005 (manage_system) 跳過：PERM_017 已有 system.manage
UPDATE public.permissions SET permission_key = 'analysis.cost.view'       WHERE permission_id = 'PERM_006';
UPDATE public.permissions SET permission_key = 'operation.order.view'     WHERE permission_id = 'PERM_007';
UPDATE public.permissions SET permission_key = 'operation.order.create'   WHERE permission_id = 'PERM_008';
UPDATE public.permissions SET permission_key = 'operation.order.edit'     WHERE permission_id = 'PERM_009';
UPDATE public.permissions SET permission_key = 'operation.order.execute'  WHERE permission_id = 'PERM_010';
UPDATE public.permissions SET permission_key = 'analysis.dashboard.view'  WHERE permission_id = 'PERM_011';
-- PERM_012 (user.manage) 不在改名清單，保留
UPDATE public.permissions SET permission_key = 'analysis.export.execute'  WHERE permission_id = 'PERM_013';
-- PERM_014 (transfer.view)、PERM_015 (transfer.create)、PERM_016 (users.manage) 保留
-- PERM_017 (system.manage) 已是正確格式，保留
-- PERM_018 (operation.stock.adjust)、PERM_019 (operation.transfer.execute) 保留
