from __future__ import annotations

"""System action service compatibility wrappers."""

from shared.core.app_runtime import (
    refresh_runtime_sheet_cache,
    run_system_reset,
    save_system_appearance,
    update_login_enabled_setting,
)


def update_login_enabled(next_value: str):
    update_login_enabled_setting(next_value)


def refresh_sheet_cache():
    refresh_runtime_sheet_cache()


def save_appearance(*, system_name: str, logo_url: str):
    save_system_appearance(system_name=system_name, logo_url=logo_url)


def clear_target_tables(target_tables: list[str], *, actor: str = "owner", target_sequence_keys: list[str] | None = None):
    run_system_reset(
        target_tables=target_tables,
        target_sequence_keys=target_sequence_keys or [],
        actor=actor,
    )
