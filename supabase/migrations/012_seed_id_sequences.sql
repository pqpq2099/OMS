-- =============================================================================
-- 012_seed_id_sequences.sql  —  初始化 id_sequences 種子資料
-- 建立時間: 2026-04-02
-- 說明:
--   確保 id_sequences 表有所有系統所需的序列行。
--   ON CONFLICT (key) DO NOTHING：若該 key 已存在則跳過，不覆蓋現有資料。
--   安全重複執行（幂等）。
--
-- 涵蓋的 sequence key（對應 shared/services/service_id.py）：
--   users, vendors, units, items, prices, unit_conversions,
--   stores, stocktakes, stocktake_lines,
--   purchase_orders, purchase_order_lines, audit_logs
--
-- 注意：
--   prefix / width 為合理預設值。若現有 id_sequences 已有既定命名規則，
--   ON CONFLICT DO NOTHING 確保不覆蓋，可安全重複執行。
-- =============================================================================

INSERT INTO public.id_sequences (key, env, prefix, width, next_value, updated_at)
VALUES
    ('users',                'prod', 'U',     4, 1, NOW()),
    ('vendors',              'prod', 'V',     4, 1, NOW()),
    ('units',                'prod', 'UNT',   4, 1, NOW()),
    ('items',                'prod', 'I',     4, 1, NOW()),
    ('prices',               'prod', 'PRC',   4, 1, NOW()),
    ('unit_conversions',     'prod', 'UC',    4, 1, NOW()),
    ('stores',               'prod', 'S',     3, 1, NOW()),
    ('stocktakes',           'prod', 'ST',    6, 1, NOW()),
    ('stocktake_lines',      'prod', 'STL',   6, 1, NOW()),
    ('purchase_orders',      'prod', 'PO',    6, 1, NOW()),
    ('purchase_order_lines', 'prod', 'POL',   6, 1, NOW()),
    ('audit_logs',           'prod', 'AUDIT', 8, 1, NOW())
ON CONFLICT (key) DO NOTHING;
