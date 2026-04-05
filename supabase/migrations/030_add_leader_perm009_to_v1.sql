-- =============================================================================
-- 030_add_leader_perm009_to_v1.sql
-- 建立時間: 2026-04-06
-- 說明:
--   OMS_V1（main）的 leader 角色缺少 PERM_009（operation.order.edit）。
--   OMS_TEST（develop）已有此對應，代表 leader 可提交叫貨單（表單儲存步驟）。
--
--   本 migration 僅套用於 OMS_V1（usaaduuqhvpfmrmimwsw）。
--   OMS_TEST 不需要，已存在。
-- =============================================================================

INSERT INTO public.role_permissions (role_id, permission_id)
VALUES ('leader', 'PERM_009')
ON CONFLICT DO NOTHING;
