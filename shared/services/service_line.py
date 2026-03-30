from __future__ import annotations

import requests
import streamlit as st


def send_line_message(*, line_message: str, store_id: str) -> bool:
    try:
        store_id = str(store_id or "").strip()

        channel_access_token = str(
            st.secrets.get("LINE_CHANNEL_ACCESS_TOKEN", "")
        ).strip()

        if not channel_access_token:
            try:
                line_bot_cfg = st.secrets.get("line_bot", {})
                channel_access_token = str(
                    line_bot_cfg.get("channel_access_token", "")
                ).strip()
            except Exception:
                channel_access_token = ""

        group_id = ""

        try:
            line_groups_cfg = st.secrets.get("line_groups", {})
            if store_id:
                group_id = str(line_groups_cfg.get(store_id, "")).strip()
        except Exception:
            group_id = ""

        if not group_id:
            group_id = str(st.secrets.get("LINE_GROUP_ID", "")).strip()

        if not channel_access_token:
            st.error(
                "缺少 LINE token，請檢查 Streamlit secrets："
                "LINE_CHANNEL_ACCESS_TOKEN 或 [line_bot].channel_access_token"
            )
            return False

        if not group_id:
            if store_id:
                st.error(
                    f"找不到分店 {store_id} 對應的 LINE 群組，"
                    "請檢查 [line_groups] 或 LINE_GROUP_ID 設定。"
                )
            else:
                st.error("缺少 LINE 群組設定，請檢查 [line_groups] 或 LINE_GROUP_ID。")
            return False

        response = requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Authorization": f"Bearer {channel_access_token}",
                "Content-Type": "application/json",
            },
            json={
                "to": group_id,
                "messages": [{"type": "text", "text": line_message}],
            },
            timeout=15,
        )

        if response.status_code == 200:
            return True

        st.error(f"LINE API 錯誤：{response.status_code} / {response.text}")
        return False

    except Exception as exc:
        st.error(f"發送 LINE 時發生錯誤：{exc}")
        return False
