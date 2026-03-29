-- =============================================================================
-- 001_init.sql  —  OMS Baseline Schema
-- 建立時間: 2026-03-30
-- 說明: 全系統資料表 DDL（baseline）。使用 CREATE TABLE IF NOT EXISTS，
--       可安全重複執行（idempotent）。
--       ALTER TABLE ... ADD COLUMN IF NOT EXISTS 補齊應用層預期欄位。
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 參考資料表（master data）
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.brands (
    brand_id        TEXT PRIMARY KEY,
    brand_name      TEXT,
    brand_name_zh   TEXT,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.units (
    unit_id         TEXT PRIMARY KEY,
    unit_name       TEXT,
    unit_name_zh    TEXT,
    unit_type       TEXT,
    unit_symbol     TEXT,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.roles (
    role_id         TEXT PRIMARY KEY,
    role_name       TEXT,
    role_name_zh    TEXT,
    role_level      INTEGER,
    is_active       BOOLEAN DEFAULT true,
    note            TEXT,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.settings (
    setting_key     TEXT PRIMARY KEY,
    setting_value   TEXT,
    updated_at      TIMESTAMP,
    updated_by      TEXT
);

CREATE TABLE IF NOT EXISTS public.id_sequences (
    key             TEXT PRIMARY KEY,
    env             TEXT,
    prefix          TEXT,
    width           INTEGER,
    next_value      INTEGER,
    updated_at      TIMESTAMP,
    updated_by      TEXT
);

-- -----------------------------------------------------------------------------
-- 組織 / 人員
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.stores (
    store_id        TEXT PRIMARY KEY,
    brand_id        TEXT,
    store_name      TEXT,
    store_name_zh   TEXT,
    store_code      TEXT,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.vendors (
    vendor_id       TEXT PRIMARY KEY,
    brand_id        TEXT,
    vendor_code     TEXT,
    vendor_name     TEXT,
    vendor_name_zh  TEXT,
    contact_name    TEXT,
    phone           TEXT,
    line_id         TEXT,
    notes           TEXT,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.users (
    user_id             TEXT PRIMARY KEY,
    account_code        TEXT UNIQUE,
    email               TEXT,
    display_name        TEXT,
    password_hash       TEXT,
    must_change_password BOOLEAN DEFAULT false,
    role_id             TEXT,
    store_scope         TEXT,
    is_active           BOOLEAN DEFAULT true,
    last_login_at       TIMESTAMP,
    created_at          TIMESTAMP,
    created_by          TEXT,
    updated_at          TIMESTAMP,
    updated_by          TEXT,
    rule_check          TEXT
);

-- LINE 通知群組（store_id -> LINE group_id 對應）
CREATE TABLE IF NOT EXISTS public.line_groups (
    store_id        TEXT PRIMARY KEY,
    line_group_id   TEXT NOT NULL,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMP DEFAULT now(),
    updated_at      TIMESTAMP DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 品項 / 規格 / 價格
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.items (
    item_id             TEXT PRIMARY KEY,
    brand_id            TEXT,
    default_vendor_id   TEXT,
    item_name           TEXT,
    item_name_zh        TEXT,
    item_type           TEXT,
    base_unit           TEXT,
    default_stock_unit  TEXT,
    default_order_unit  TEXT,
    orderable_units     TEXT,
    is_active           BOOLEAN DEFAULT true,
    created_at          TIMESTAMP,
    updated_at          TIMESTAMP,
    category            TEXT,
    spec_value          TEXT,
    spec_unit           TEXT,
    pack_unit           TEXT,
    pack_qty            NUMERIC,
    outer_unit          TEXT
);

CREATE TABLE IF NOT EXISTS public.item_specs (
    spec_id         TEXT PRIMARY KEY,
    item_id         TEXT,
    spec_name       TEXT,
    stock_unit      TEXT,
    order_unit      TEXT,
    orderable_units TEXT,
    spec_note       TEXT,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.prices (
    price_id        TEXT PRIMARY KEY,
    item_id         TEXT,
    spec_id         TEXT,
    unit_price      NUMERIC,
    price_unit      TEXT,
    effective_date  DATE,
    end_date        DATE,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.unit_conversions (
    conversion_id   TEXT PRIMARY KEY,
    spec_id         TEXT,
    item_id         TEXT,
    from_unit       TEXT,
    to_unit         TEXT,
    ratio           NUMERIC,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 交易流水
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.transactions (
    txn_id      TEXT PRIMARY KEY,
    txn_date    DATE,
    store_id    TEXT,
    vendor_id   TEXT,
    item_id     TEXT,
    spec_id     TEXT,
    item_name   TEXT,
    txn_type    TEXT,
    qty         NUMERIC,
    unit        TEXT,
    base_qty    NUMERIC,
    unit_price  NUMERIC,
    amount      NUMERIC,
    ref_type    TEXT,
    ref_id      TEXT,
    note        TEXT,
    created_by  TEXT,
    created_at  TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 盤點
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.stocktakes (
    stocktake_id    TEXT PRIMARY KEY,
    store_id        TEXT,
    stocktake_date  DATE,
    vendor_id       TEXT,
    stocktake_type  TEXT,               -- 'initial' | 'regular'
    status          TEXT,
    note            TEXT,
    created_at      TIMESTAMP,
    created_by      TEXT,
    updated_at      TIMESTAMP,
    updated_by      TEXT
);

CREATE TABLE IF NOT EXISTS public.stocktake_lines (
    id              SERIAL,             -- DB autoincrement（不對外暴露）
    stocktake_line_id TEXT,
    stocktake_id    TEXT,
    store_id        TEXT,
    vendor_id       TEXT,
    item_id         TEXT,
    item_name       TEXT,
    qty             NUMERIC,            -- 應用層紀錄值（同 stock_qty）
    stock_qty       NUMERIC,
    unit_id         TEXT,               -- 應用層單位 ID
    stock_unit_id   TEXT,
    stock_unit      TEXT,
    base_qty        NUMERIC,
    base_unit       TEXT,
    suggested_order_qty NUMERIC,
    order_qty       NUMERIC,
    order_unit_id   TEXT,
    note            TEXT,
    created_at      TIMESTAMP,
    created_by      TEXT,
    updated_at      TIMESTAMP,
    updated_by      TEXT,
    PRIMARY KEY (id)
);

-- -----------------------------------------------------------------------------
-- 叫貨
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.purchase_orders (
    po_id       TEXT PRIMARY KEY,
    po_date     DATE,
    order_date  DATE,
    expected_date DATE,
    delivery_date DATE,
    store_id    TEXT,
    vendor_id   TEXT,
    status      TEXT,
    note        TEXT,
    created_at  TIMESTAMP,
    created_by  TEXT,
    updated_at  TIMESTAMP,
    updated_by  TEXT
);

CREATE TABLE IF NOT EXISTS public.purchase_order_lines (
    id          SERIAL,                 -- DB autoincrement（不對外暴露）
    po_line_id  TEXT,
    po_id       TEXT,
    store_id    TEXT,
    vendor_id   TEXT,
    item_id     TEXT,
    spec_id     TEXT,
    item_name   TEXT,
    qty         NUMERIC,
    order_qty   NUMERIC,
    unit_id     TEXT,
    order_unit  TEXT,
    base_qty    NUMERIC,
    base_unit   TEXT,
    unit_price  NUMERIC,
    amount      NUMERIC,
    note        TEXT,
    delivery_date DATE,
    created_at  TIMESTAMP,
    created_by  TEXT,
    updated_at  TIMESTAMP,
    updated_by  TEXT,
    PRIMARY KEY (id)
);

-- -----------------------------------------------------------------------------
-- 稽核日誌
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.audit_logs (
    audit_id    TEXT PRIMARY KEY,
    ts          TIMESTAMP,
    user_id     TEXT,
    action      TEXT,
    table_name  TEXT,
    entity_id   TEXT,
    before_json TEXT,
    after_json  TEXT,
    note        TEXT
);

-- =============================================================================
-- ALTER TABLE — 補齊應用層預期但 DB 可能缺少的欄位（idempotent）
-- =============================================================================

-- stocktakes: 補 stocktake_type（若升版前已存在則略過）
ALTER TABLE public.stocktakes ADD COLUMN IF NOT EXISTS stocktake_type TEXT;

-- stocktake_lines: 補應用層寫入欄位
ALTER TABLE public.stocktake_lines ADD COLUMN IF NOT EXISTS qty         NUMERIC;
ALTER TABLE public.stocktake_lines ADD COLUMN IF NOT EXISTS unit_id     TEXT;
ALTER TABLE public.stocktake_lines ADD COLUMN IF NOT EXISTS base_unit   TEXT;
ALTER TABLE public.stocktake_lines ADD COLUMN IF NOT EXISTS created_by  TEXT;
ALTER TABLE public.stocktake_lines ADD COLUMN IF NOT EXISTS updated_by  TEXT;

-- purchase_order_lines: 補應用層寫入欄位
ALTER TABLE public.purchase_order_lines ADD COLUMN IF NOT EXISTS base_unit   TEXT;
ALTER TABLE public.purchase_order_lines ADD COLUMN IF NOT EXISTS created_by  TEXT;
ALTER TABLE public.purchase_order_lines ADD COLUMN IF NOT EXISTS updated_by  TEXT;
