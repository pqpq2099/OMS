-- =============================================================================
-- 013_rpc_fill_missing_cols.sql  —  補齊 RPC INSERT 遺漏欄位
-- 建立時間: 2026-04-02
-- 說明:
--   009 版本的 rpc_save_order_transaction 遺漏以下欄位（DB 已存在，Python payload
--   已送出，但 SQL INSERT 清單未包含，導致欄位長期為 NULL）：
--
--   A. stocktakes
--      補寫：stocktake_type
--      策略：INSERT 時寫入，ON CONFLICT DO UPDATE 不覆蓋（保留原始 type）
--
--   B. stocktake_lines
--      補寫：qty, unit_id, base_unit, created_by, updated_by
--      策略：INSERT 全補；ON CONFLICT DO UPDATE 補 qty/unit_id/base_unit/updated_by
--            （created_by 不加入 DO UPDATE，避免覆蓋原建立者）
--
--   C. purchase_order_lines
--      補寫：base_unit, created_by, updated_by
--      策略：INSERT 全補；ON CONFLICT DO UPDATE 補 base_unit/updated_by
--            （created_by 不加入 DO UPDATE，避免覆蓋原建立者）
--
-- 不變事項：
--   - 函式參數 (p_payload jsonb) 不變
--   - 交易結構不變
--   - ON CONFLICT 衝突鍵不變
--   - purchase_orders 邏輯不變（已在 009 補齊）
--   - audit_logs 邏輯不變
--   - GRANT/REVOKE 規則不變
-- =============================================================================

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
