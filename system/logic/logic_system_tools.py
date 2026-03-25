from __future__ import annotations

from system.services import system_actions


def apply_login_enabled_toggle(next_value: str):
    system_actions.update_login_enabled(next_value)
