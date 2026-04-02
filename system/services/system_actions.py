from __future__ import annotations

"""System action service compatibility wrappers."""

from shared.core.app_runtime import update_login_enabled_setting


def update_login_enabled(next_value: str):
    update_login_enabled_setting(next_value)
