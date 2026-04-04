-- =============================================================================
-- 026_seed_adjustment_transfer_permissions.sql
-- 建立時間: 2026-04-05
-- 說明:
--   1. 新增兩個 permission key：
--        PERM_018: operation.stock.adjust  → store_manager 以上
--        PERM_019: operation.transfer.execute → leader 以上
--   2. 新增 id_sequences 種子資料（新三張表）
--
--   安全可重複執行（ON CONFLICT DO NOTHING）。
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. 新增 permission keys
-- -----------------------------------------------------------------------------
INSERT INTO public.permissions (permission_id, permission_key)
VALUES
    ('PERM_018', 'operation.stock.adjust'),
    ('PERM_019', 'operation.transfer.execute')
ON CONFLICT (permission_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 2. 新增 role_permissions 對應
--    operation.stock.adjust: store_manager, test_store_manager, admin, test_admin, owner
--    operation.transfer.execute: leader, test_leader, store_manager, test_store_manager, admin, test_admin, owner
-- -----------------------------------------------------------------------------
INSERT INTO public.role_permissions (role_id, permission_id)
VALUES
    -- operation.stock.adjust
    ('store_manager',      'PERM_018'),
    ('test_store_manager', 'PERM_018'),
    ('admin',              'PERM_018'),
    ('test_admin',         'PERM_018'),
    ('owner',              'PERM_018'),
    -- operation.transfer.execute
    ('leader',             'PERM_019'),
    ('test_leader',        'PERM_019'),
    ('store_manager',      'PERM_019'),
    ('test_store_manager', 'PERM_019'),
    ('admin',              'PERM_019'),
    ('test_admin',         'PERM_019'),
    ('owner',              'PERM_019')
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 3. id_sequences 種子資料
-- -----------------------------------------------------------------------------
INSERT INTO public.id_sequences (key, env, prefix, width, next_value, updated_at)
VALUES
    ('stock_adjustments',   'prod', 'ADJ',  6, 1, NOW()),
    ('stock_transfers',     'prod', 'TRF',  6, 1, NOW()),
    ('stock_transfer_lines','prod', 'TRFL', 6, 1, NOW())
ON CONFLICT (key) DO NOTHING;
