# ============================================================
# ORIVIA OMS
# 檔案：oms_core.py
# 說明：ORIVIA OMS 核心整合模組（相容層）
# 功能：保留既有 import 路徑，實際實作已分流到 shared/*。
# ============================================================

from __future__ import annotations

from shared.utils.common_helpers import (
    _clean_option_list,
    _get_active_df,
    _item_display_name,
    _label_store,
    _label_vendor,
    _norm,
    _now_ts,
    _parse_date,
    _safe_float,
    _sort_items_for_operation,
    _status_hint,
    _to_bool,
)
from shared.services.id_allocation import _make_id, allocate_ids
from shared.services.report_calculations import (
    _build_inventory_history_summary_df,
    _build_latest_item_metrics_df,
    _build_purchase_detail_df,
    _build_purchase_summary_df,
    _build_stock_detail_df,
    _coalesce_columns,
    _get_last_po_summary,
    _get_latest_price_for_item,
    _get_latest_stock_qty_in_display_unit,
    _parse_vendor_id_from_note,
    _sum_purchase_qty_in_display_unit,
    get_base_unit_cost,
)
from shared.services.data_backend import (
    BASE_DIR,
    LOCAL_SERVICE_ACCOUNT,
    _get_header_remote,
    _get_runtime_df_cache,
    _get_runtime_header_cache,
    _get_runtime_table_cache,
    _get_table_version_map,
    _read_table_remote,
    _session_df_cache_get,
    _session_df_cache_set,
    _table_versions_signature,
    append_rows_by_header,
    bust_cache,
    get_header,
    get_row_index_map,
    get_table_version,
    get_table_versions,
    read_table,
    update_row_by_match,
)
from shared.utils.ui_style import (
    PLOTLY_CONFIG,
    apply_global_style,
    apply_table_report_style,
    export_csv_button,
    render_report_dataframe,
)

__all__ = [name for name in globals() if not name.startswith("__")]
