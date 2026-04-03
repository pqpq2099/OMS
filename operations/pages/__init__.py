"""Public entry points for operations pages.

Router-facing names are aligned here. In particular,
`page_order_message_detail` remains the stable public name even though the
implementation currently lives in `page_order_result.py`.
"""

from .page_select_store import page_select_store
from .page_select_vendor import page_select_vendor
from .page_order import page_order
from .page_order_result import page_order_message_detail
from .page_order_result import page_order_message_detail as page_order_result

__all__ = [
    "page_select_store",
    "page_select_vendor",
    "page_order",
    "page_order_result",
    "page_order_message_detail",
]
