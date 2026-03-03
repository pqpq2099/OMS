import streamlit as st

def send_line_message(message: str) -> bool:
    import requests, json
    try:
        token = st.secrets["line_bot"]["channel_access_token"]
        current_store = st.session_state.get("store", "")
        target_id = st.secrets.get("line_groups", {}).get(current_store)
        if not target_id:
            target_id = st.secrets["line_bot"].get("user_id")
        if not target_id:
            return False

        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        payload = {"to": target_id, "messages": [{"type": "text", "text": message}]}
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        return response.status_code == 200
    except Exception:
        return False
