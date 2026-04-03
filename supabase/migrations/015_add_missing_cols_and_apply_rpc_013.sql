-- =============================================================================
-- 015_add_missing_cols_and_apply_rpc_013.sql
-- 建立時間: 2026-04-03
-- 說明:
--   013_rpc_fill_missing_cols.sql 的內容假設 DB 已有目標欄位（註解寫「DB 已存在」），
--   但 live DB 的 initial_schema 與 001_init.sql 不一致，實際欄位並不存在。
--   直接套用 013 會造成 RPC 函式 INSERT 不存在欄位 → runtime error → 主線中斷。
--
--   本 migration 分兩步修正：
--   Step 1: ADD COLUMN IF NOT EXISTS 補齊三張表缺少的欄位（幂等安全）
--   Step 2: CREATE OR REPLACE FUNCTION（與 013 邏輯完全相同）
--
--   補齊欄位：
--     stocktakes:           stocktake_type (nullable text)
--     stocktake_lines:      qty, unit_id, base_unit, created_by, updated_by
--     purchase_order_lines: base_unit, created_by, updated_by
--
--   stocktake_type 說明：
--     Python payload 已於 H1 fix 移除 stocktake_type 傳送，
--     RPC 使用 NULLIF(v_st->>'stocktake_type','') → 永遠寫入 NULL，無業務影響。
--     補欄位目的是讓 RPC 函式可正常編譯與執行。
--
--   安全性：
--     - ADD COLUMN IF NOT EXISTS：幂等，二次執行無副作用
--     - CREATE OR REPLACE FUNCTION：幂等，二次執行無副作用
--     - 所有新增欄位均為 nullable，不影響既有資料列
--     - ON CONFLICT 衝突鍵與 partial index 保持不變
-- =============================================================================

-- ── Step 1-A: stocktakes 補 stocktake_type ───────────────────────────────
ALTER TABLE public.stocktakes
    ADD COLUMN IF NOT EXISTS stocktake_type text;

-- ── Step 1-B: stocktake_lines 補 qty / unit_id / base_unit / created_by / updated_by ──
ALTER TABLE public.stocktake_lines
    ADD COLUMN IF NOT EXISTS qty        numeric,
    ADD COLUMN IF NOT EXISTS unit_id    text,
    ADD COLUMN IF NOT EXISTS base_unit  text,
    ADD COLUMN IF NOT EXISTS created_by text,
    ADD COLUMN IF NOT EXISTS updated_by text;

-- ── Step 1-C: purchase_order_lines 補 base_unit / created_by / updated_by ──
ALTER TABLE public.purchase_order_lines
    ADD COLUMN IF NOT EXISTS base_unit  text,
    ADD COLUMN IF NOT EXISTS created_by text,
    ADD COLUMN IF NOT EXISTS updated_by text;

-- ── Step 2: CREATE OR REPLACE FUNCTION（與 013 完全相同）────────────────
CREATE OR REPLACE FUNCTION public.rpc_save_order_transaction(p_payload jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_st     jsonb := p_payload -> 'stocktake';
    v_stls   jsonb := p_payload -> 'stocktake_lines';
    v_po     jsonb := p_payload -> 'purchase_order';
    v_pols   jsonb := p_payload -> 'purchase_order_lines';
    v_audits jsonb := p_payload -> 'audit_logs';
    v_row    jsonb;
BEGIN
    -- 1. Upsert stocktake
    --    補寫：stocktake_type（INSERT 時寫入；DO UPDATE 不覆蓋，保留原始 type）
    IF v_st IS NOT NULL AND v_st != 'null'::jsonb THEN
        INSERT INTO public.stocktakes (
            stocktake_id, store_id, vendor_id, stocktake_date,
            stocktake_type,
            status, note, created_at, created_by, updated_at, updated_by
        ) VALUES (
            v_st->>'stocktake_id',
            v_st->>'store_id',
            v_st->>'vendor_id',
            (v_st->>'stocktake_date')::date,
            NULLIF(v_st->>'stocktake_type', ''),
            v_st->>'status',
            v_st->>'note',
            (v_st->>'created_at')::timestamptz,
            v_st->>'created_by',
            (v_st->>'updated_at')::timestamptz,
            v_st->>'updated_by'
        )
        ON CONFLICT (stocktake_id) DO UPDATE SET
            store_id       = EXCLUDED.store_id,
            vendor_id      = EXCLUDED.vendor_id,
            stocktake_date = EXCLUDED.stocktake_date,
            status         = EXCLUDED.status,
            note           = EXCLUDED.note,
            updated_at     = EXCLUDED.updated_at,
            updated_by     = EXCLUDED.updated_by;
            -- stocktake_type 不加入 DO UPDATE：保留初次建立時的 type，不被重複儲存覆蓋
    END IF;

    -- 2. Upsert stocktake_lines
    --    補寫：qty, unit_id, base_unit, created_by, updated_by
    IF v_stls IS NOT NULL AND v_stls != 'null'::jsonb THEN
        FOR v_row IN SELECT value FROM jsonb_array_elements(v_stls) LOOP
            INSERT INTO public.stocktake_lines (
                stocktake_line_id, stocktake_id, store_id, vendor_id,
                item_id, item_name,
                qty, stock_qty,
                unit_id, stock_unit, stock_unit_id,
                base_qty, base_unit,
                created_at, created_by, updated_at, updated_by
            ) VALUES (
                v_row->>'stocktake_line_id',
                v_row->>'stocktake_id',
                v_row->>'store_id',
                v_row->>'vendor_id',
                v_row->>'item_id',
                v_row->>'item_name',
                (v_row->>'qty')::numeric,
                (v_row->>'stock_qty')::numeric,
                v_row->>'unit_id',
                v_row->>'stock_unit',
                v_row->>'stock_unit_id',
                (v_row->>'base_qty')::numeric,
                v_row->>'base_unit',
                (v_row->>'created_at')::timestamptz,
                v_row->>'created_by',
                (v_row->>'updated_at')::timestamptz,
                v_row->>'updated_by'
            )
            ON CONFLICT (stocktake_line_id)
                WHERE stocktake_line_id IS NOT NULL AND stocktake_line_id <> ''
            DO UPDATE SET
                stocktake_id  = EXCLUDED.stocktake_id,
                store_id      = EXCLUDED.store_id,
                vendor_id     = EXCLUDED.vendor_id,
                item_id       = EXCLUDED.item_id,
                item_name     = EXCLUDED.item_name,
                qty           = EXCLUDED.qty,
                stock_qty     = EXCLUDED.stock_qty,
                unit_id       = EXCLUDED.unit_id,
                stock_unit    = EXCLUDED.stock_unit,
                stock_unit_id = EXCLUDED.stock_unit_id,
                base_qty      = EXCLUDED.base_qty,
                base_unit     = EXCLUDED.base_unit,
                updated_at    = EXCLUDED.updated_at,
                updated_by    = EXCLUDED.updated_by;
                -- created_by 不加入 DO UPDATE：保留原始建立者
        END LOOP;
    END IF;

    -- 3. Upsert purchase_order（009 已補齊 stocktake_id，本次不變）
    IF v_po IS NOT NULL AND v_po != 'null'::jsonb THEN
        INSERT INTO public.purchase_orders (
            po_id, stocktake_id, store_id, vendor_id,
            po_date, order_date, expected_date, delivery_date,
            status, created_at, created_by, updated_at, updated_by
        ) VALUES (
            v_po->>'po_id',
            NULLIF(v_po->>'stocktake_id', ''),
            v_po->>'store_id',
            v_po->>'vendor_id',
            (v_po->>'po_date')::date,
            (v_po->>'order_date')::date,
            (v_po->>'expected_date')::date,
            (v_po->>'delivery_date')::date,
            v_po->>'status',
            (v_po->>'created_at')::timestamptz,
            v_po->>'created_by',
            (v_po->>'updated_at')::timestamptz,
            v_po->>'updated_by'
        )
        ON CONFLICT (po_id) DO UPDATE SET
            stocktake_id  = EXCLUDED.stocktake_id,
            store_id      = EXCLUDED.store_id,
            vendor_id     = EXCLUDED.vendor_id,
            po_date       = EXCLUDED.po_date,
            order_date    = EXCLUDED.order_date,
            expected_date = EXCLUDED.expected_date,
            delivery_date = EXCLUDED.delivery_date,
            status        = EXCLUDED.status,
            updated_at    = EXCLUDED.updated_at,
            updated_by    = EXCLUDED.updated_by;
    END IF;

    -- 4. Upsert purchase_order_lines
    --    補寫：base_unit, created_by, updated_by
    IF v_pols IS NOT NULL AND v_pols != 'null'::jsonb THEN
        FOR v_row IN SELECT value FROM jsonb_array_elements(v_pols) LOOP
            INSERT INTO public.purchase_order_lines (
                po_line_id, po_id, store_id, vendor_id,
                item_id, item_name,
                qty, order_qty, unit_id, order_unit,
                base_qty, base_unit, unit_price, amount,
                delivery_date, created_at, created_by, updated_at, updated_by
            ) VALUES (
                v_row->>'po_line_id',
                v_row->>'po_id',
                v_row->>'store_id',
                v_row->>'vendor_id',
                v_row->>'item_id',
                v_row->>'item_name',
                (v_row->>'qty')::numeric,
                (v_row->>'order_qty')::numeric,
                v_row->>'unit_id',
                v_row->>'order_unit',
                (v_row->>'base_qty')::numeric,
                v_row->>'base_unit',
                (v_row->>'unit_price')::numeric,
                (v_row->>'amount')::numeric,
                (v_row->>'delivery_date')::date,
                (v_row->>'created_at')::timestamptz,
                v_row->>'created_by',
                (v_row->>'updated_at')::timestamptz,
                v_row->>'updated_by'
            )
            ON CONFLICT (po_line_id)
                WHERE po_line_id IS NOT NULL AND po_line_id <> ''
            DO UPDATE SET
                po_id         = EXCLUDED.po_id,
                store_id      = EXCLUDED.store_id,
                vendor_id     = EXCLUDED.vendor_id,
                item_id       = EXCLUDED.item_id,
                item_name     = EXCLUDED.item_name,
                qty           = EXCLUDED.qty,
                order_qty     = EXCLUDED.order_qty,
                unit_id       = EXCLUDED.unit_id,
                order_unit    = EXCLUDED.order_unit,
                base_qty      = EXCLUDED.base_qty,
                base_unit     = EXCLUDED.base_unit,
                unit_price    = EXCLUDED.unit_price,
                amount        = EXCLUDED.amount,
                delivery_date = EXCLUDED.delivery_date,
                updated_at    = EXCLUDED.updated_at,
                updated_by    = EXCLUDED.updated_by;
                -- created_by 不加入 DO UPDATE：保留原始建立者
        END LOOP;
    END IF;

    -- 5. Insert audit_logs（不變）
    IF v_audits IS NOT NULL AND v_audits != 'null'::jsonb THEN
        FOR v_row IN SELECT value FROM jsonb_array_elements(v_audits) LOOP
            INSERT INTO public.audit_logs (
                audit_id, ts, user_id, action,
                table_name, entity_id, before_json, after_json, note
            ) VALUES (
                v_row->>'audit_id',
                (v_row->>'ts')::timestamptz,
                v_row->>'user_id',
                v_row->>'action',
                v_row->>'table_name',
                v_row->>'entity_id',
                v_row->>'before_json',
                v_row->>'after_json',
                v_row->>'note'
            )
            ON CONFLICT (audit_id) DO NOTHING;
        END LOOP;
    END IF;

    RETURN jsonb_build_object(
        'ok',           true,
        'stocktake_id', COALESCE(v_st->>'stocktake_id', ''),
        'po_id',        COALESCE(CASE WHEN v_po IS NOT NULL AND v_po != 'null'::jsonb THEN v_po->>'po_id' END, '')
    );
END;
$$;

REVOKE ALL ON FUNCTION public.rpc_save_order_transaction(jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.rpc_save_order_transaction(jsonb) FROM anon;
REVOKE ALL ON FUNCTION public.rpc_save_order_transaction(jsonb) FROM authenticated;
GRANT  EXECUTE ON FUNCTION public.rpc_save_order_transaction(jsonb) TO service_role;
