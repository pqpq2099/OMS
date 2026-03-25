from __future__ import annotations

from collections.abc import Callable, Iterable

import streamlit as st


def goto(step: str):
    """統一切頁動作，避免各頁重複寫 step + rerun。"""
    st.session_state.step = step
    st.rerun()


def sidebar_step_button(label: str, step: str, key: str, *, width: str = "stretch"):
    """側邊欄切頁按鈕。"""
    if st.button(label, width=width, key=key):
        goto(step)


def render_step_buttons(items: Iterable[dict]):
    """依設定渲染多個側邊欄按鈕。"""
    for item in items:
        if not item.get("visible", True):
            continue
        sidebar_step_button(
            label=item["label"],
            step=item["step"],
            key=item["key"],
            width=item.get("width", "stretch"),
        )


def resolve_step_alias(step: str, aliases: dict[str, str] | None = None) -> str:
    """將舊 step 名稱映射為目前正式 step。"""
    if not aliases:
        return step
    return aliases.get(step, step)


def route_step(
    step: str,
    routes: dict[str, Callable[[], None]],
    default_page: Callable[[], None],
    *,
    aliases: dict[str, str] | None = None,
):
    """依 step 執行對應頁面，支援舊 step 別名轉址，找不到時回預設頁。"""
    normalized_step = resolve_step_alias(step, aliases)
    if normalized_step != step:
        st.session_state.step = normalized_step
    page = routes.get(normalized_step, default_page)
    page()
