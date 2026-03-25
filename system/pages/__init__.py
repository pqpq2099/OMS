"""Public entry points for system pages."""

from .page_appearance_settings import page_appearance_settings
from .page_system_info import page_system_info
from .page_system_maintenance import page_system_maintenance
from .page_system_tools import page_system_tools

__all__ = [
    "page_appearance_settings",
    "page_system_info",
    "page_system_maintenance",
    "page_system_tools",
]
