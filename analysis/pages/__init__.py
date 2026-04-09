"""Public entry points for analysis pages.

Router-facing names are defined here as the single source of truth for
analysis page imports. Any filename/function-name differences are aligned
through aliases in this package, not in the router.
"""

from .page_export import page_export_report
from .page_inventory_analysis import page_inventory_analysis
from .page_order_history import page_order_history
from .page_reports import (
    page_analysis,
    page_cost_debug,
    page_export,
    page_stock_order_compare,
    page_usage_conversion,
    page_view_history,
)

__all__ = [
    "page_export_report",
    "page_inventory_analysis",
    "page_order_history",
    "page_analysis",
    "page_cost_debug",
    "page_export",
    "page_stock_order_compare",
    "page_usage_conversion",
    "page_view_history",
]
