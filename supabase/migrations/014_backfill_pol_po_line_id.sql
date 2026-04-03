-- =============================================================================
-- 014_backfill_pol_po_line_id.sql  —  一次性回填歷史 purchase_order_lines.po_line_id
-- 建立時間: 2026-04-03
-- 說明:
--   267 筆歷史資料因舊寫入路徑未填入 po_line_id，導致：
--     ON CONFLICT (po_line_id) WHERE po_line_id IS NOT NULL AND po_line_id <> ''
--   部分唯一索引永不觸發，重新儲存同一 PO 會產生重複明細行。
--
--   本 migration 為 po_line_id IS NULL OR po_line_id = '' 的行補入
--   POL_000001 ~ POL_000267，與現行 id_allocation 規則完全一致。
--
-- ID 規則（對應 id_sequences）:
--   key = 'purchase_order_lines', env = 'prod'
--   prefix = 'POL_', width = 6
--   → POL_000001, POL_000002, ..., POL_000267
--
-- id_sequences 狀態:
--   執行前 next_value = 268（序列已正確超前），回填後無需調整。
--   本 migration 含安全性 UPDATE：確保 next_value >= max 流水 + 1。
--
-- 排序規則:
--   ORDER BY created_at, po_id, item_id, id
--   — id 為 integer serial PK，保證排序穩定唯一
--
-- 安全性（幂等）:
--   外層 IF EXISTS 確保若無 null 行則直接跳過，二次執行無副作用。
--   不覆蓋已有非空 po_line_id 的行（WHERE 條件限定）。
-- =============================================================================

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    -- 確認是否有需要回填的行
    SELECT COUNT(*) INTO v_count
    FROM public.purchase_order_lines
    WHERE po_line_id IS NULL OR po_line_id = '';

    IF v_count > 0 THEN
        -- 依穩定排序指派 POL_XXXXXX
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    ORDER BY created_at, po_id, item_id, id
                ) AS rn
            FROM public.purchase_order_lines
            WHERE po_line_id IS NULL OR po_line_id = ''
        )
        UPDATE public.purchase_order_lines pol
        SET po_line_id = 'POL_' || LPAD(ranked.rn::text, 6, '0')
        FROM ranked
        WHERE pol.id = ranked.id;

        RAISE NOTICE '✅ Backfilled % rows with po_line_id (POL_000001 ~ POL_%).',
            v_count,
            LPAD(v_count::text, 6, '0');
    ELSE
        RAISE NOTICE '⏭ No null po_line_id rows found. Migration already applied or not needed.';
    END IF;

    -- 安全性校正：確保 id_sequences.next_value >= max 流水 + 1
    UPDATE public.id_sequences
    SET
        next_value = GREATEST(
            next_value::integer,
            (
                SELECT COALESCE(
                    MAX(CAST(SUBSTRING(po_line_id FROM 5) AS INTEGER)),
                    0
                ) + 1
                FROM public.purchase_order_lines
                WHERE po_line_id ~ '^POL_[0-9]{6}$'
            )
        ),
        updated_at = NOW()
    WHERE key = 'purchase_order_lines'
      AND env = 'prod';

    RAISE NOTICE '✅ id_sequences.next_value verified/updated for purchase_order_lines.';
END $$;
