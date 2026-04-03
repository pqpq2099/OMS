from __future__ import annotations

# ---------------------------------------------------------------------------
# TABLE_CONTRACT — 全系統唯一資料表契約
#
# 每個 table 定義三個鍵：
#   primary_key     : 應用層主鍵（供 data_backend 做 upsert / update）
#   required_columns: 寫入時不可為空的欄位清單
#   columns_order   : 欄位順序（與 Supabase schema 一致，供 fallback header 使用）
#
# 注意：
#   - purchase_order_lines / stocktake_lines 的 DB 自增 PK 為 "id"，
#     但應用層以 po_line_id / stocktake_line_id 作為業務識別鍵，
#     primary_key 填應用層鍵，columns_order 保留 "id" 欄位（讀取時存在）。
#   - is_active / boolean 欄位不列入 required_columns，允許 NULL。
# ---------------------------------------------------------------------------

TABLE_CONTRACT: dict[str, dict] = {
    "items": {
        "primary_key": "item_id",
        "required_columns": ["item_id"],
        "columns_order": [
            "item_id", "brand_id", "default_vendor_id", "item_name", "item_name_zh",
            "item_type", "base_unit", "default_stock_unit", "default_order_unit",
            "orderable_units", "is_active", "created_at", "updated_at",
            "category", "note", "spec_value", "spec_unit", "pack_unit", "pack_qty", "outer_unit",
            "require_price",
        ],
    },
    "vendors": {
        "primary_key": "vendor_id",
        "required_columns": ["vendor_id"],
        "columns_order": [
            "vendor_id", "brand_id", "vendor_code", "vendor_name", "vendor_name_zh",
            "contact_name", "phone", "line_id", "notes", "is_active",
            "created_at", "updated_at",
        ],
    },
    "purchase_orders": {
        "primary_key": "po_id",
        "required_columns": ["po_id", "store_id", "vendor_id"],
        "columns_order": [
            "po_id", "stocktake_id", "po_date", "order_date", "expected_date", "delivery_date",
            "store_id", "vendor_id", "status", "note",
            "created_at", "created_by", "updated_at", "updated_by",
        ],
    },
    "purchase_order_lines": {
        "primary_key": "po_line_id",
        "required_columns": ["po_line_id", "po_id", "item_id"],
        "columns_order": [
            "id", "po_line_id", "po_id", "store_id", "vendor_id",
            "item_id", "spec_id", "item_name", "qty", "order_qty",
            "unit_id", "order_unit", "base_qty", "unit_price", "amount",
            "note", "delivery_date", "created_at", "updated_at",
        ],
    },
    "stocktakes": {
        "primary_key": "stocktake_id",
        "required_columns": ["stocktake_id", "store_id", "vendor_id"],
        "columns_order": [
            "stocktake_id", "store_id", "stocktake_date", "vendor_id",
            "status", "note",
            "created_at", "created_by", "updated_at", "updated_by",
        ],
    },
    "stocktake_lines": {
        "primary_key": "stocktake_line_id",
        "required_columns": ["stocktake_line_id", "stocktake_id", "item_id"],
        "columns_order": [
            "id", "stocktake_line_id", "stocktake_id", "store_id", "vendor_id",
            "item_id", "item_name", "stock_qty", "stock_unit_id", "stock_unit",
            "base_qty", "suggested_order_qty", "order_qty", "order_unit_id",
            "note", "created_at", "updated_at",
        ],
    },
    "users": {
        "primary_key": "user_id",
        "required_columns": ["user_id"],
        "columns_order": [
            "user_id", "account_code", "email", "display_name", "password_hash",
            "must_change_password", "role_id", "store_scope", "is_active",
            "last_login_at", "created_at", "created_by", "updated_at", "updated_by",
            "rule_check",
        ],
    },
    "stores": {
        "primary_key": "store_id",
        "required_columns": ["store_id"],
        "columns_order": [
            "store_id", "brand_id", "store_name", "store_name_zh", "store_code",
            "is_active", "created_at", "updated_at", "updated_by",
        ],
    },
    "line_groups": {
        "primary_key": "store_id",
        "required_columns": ["store_id", "line_group_id"],
        "columns_order": [
            "store_id", "line_group_id", "is_active", "created_at", "updated_at",
        ],
    },
    "units": {
        "primary_key": "unit_id",
        "required_columns": ["unit_id"],
        "columns_order": [
            "unit_id", "brand_id", "unit_name", "unit_name_zh", "unit_type", "unit_symbol",
            "is_active", "created_at", "updated_at",
        ],
    },
    "prices": {
        "primary_key": "price_id",
        "required_columns": ["price_id", "item_id"],
        "columns_order": [
            "price_id", "item_id", "unit_price", "price_unit",
            "effective_date", "end_date", "is_active", "created_at", "updated_at",
        ],
    },
    "unit_conversions": {
        "primary_key": "conversion_id",
        "required_columns": ["conversion_id", "item_id"],
        "columns_order": [
            "conversion_id", "item_id", "from_unit", "to_unit",
            "ratio", "is_active", "created_at", "updated_at",
        ],
    },
    "audit_logs": {
        "primary_key": "audit_id",
        "required_columns": ["audit_id"],
        "columns_order": [
            "audit_id", "ts", "user_id", "action", "table_name",
            "entity_id", "before_json", "after_json", "note",
        ],
    },
}

__all__ = ["TABLE_CONTRACT"]
