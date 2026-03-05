import streamlit as st
from datetime import date

st.set_page_config(page_title="OMS Compact (No :has)", layout="wide")

# ============================================================
# CSS
# ============================================================
st.markdown("""
<style>
.block-container{
  max-width: 980px;
  padding: 16px 16px 32px;
}

/* 讓 columns 在手機也不要自動直排 */
div[data-testid="stHorizontalBlock"]{
  flex-wrap: nowrap !important;
  gap: 4px !important;
}

/* 欄位不要撐滿 */
div[data-testid="column"]{
  padding: 0 !important;
  margin: 0 !important;
  min-width: 0 !important;
}

/* ========= 小格子：text_input ========= */
div[data-testid="stTextInput"]{
  width: 62px !important;
  min-width: 62px !important;
  max-width: 62px !important;
}
div[data-testid="stTextInput"] input{
  padding: 2px 4px !important;
  font-size: 13px !important;
  line-height: 1.1 !important;
}

/* ========= 單位：radio 水平 ========= */
div[data-testid="stRadio"]{
  width: 150px !important;
  min-width: 150px !important;
  max-width: 150px !important;
}
div[data-testid="stRadio"] label{
  font-size: 13px !important;
}
div[data-testid="stRadio"] div[role="radiogroup"]{
  display: flex !important;
  flex-wrap: nowrap !important;
  gap: 6px !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] > label{
  margin: 0 !important;
  padding: 0 !important;
}

/* 卡片 */
.item-card{
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
}
.item-name{
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 4px 0;
}
.item-meta{
  font-size: 13px;
  color: #666;
  margin: 0 0 8px 0;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# Demo data
# ============================================================
items = [
    {"id": "1", "name": "測試原料", "price": 10.0},
    {"id": "2", "name": "魚", "price": 0.0},
    {"id": "3", "name": "高麗菜", "price": 50.0},
]

UNIT_OPTIONS = ["KG", "包", "箱"]

# ============================================================
# Helpers
# ============================================================
def sanitize_int_text(text: str, max_len: int = 4) -> str:
    text = (text or "").strip()
    if text == "":
        return ""
    cleaned = "".join(ch for ch in text if ch.isdigit())
    return cleaned[:max_len]

def sync_clean_input(input_key: str, value_key: str):
    raw = st.session_state.get(input_key, "")
    cleaned = sanitize_int_text(raw)
    st.session_state[input_key] = cleaned
    st.session_state[value_key] = cleaned

# ============================================================
# Header
# ============================================================
a, b = st.columns([2, 1])
with a:
    st.selectbox("分店", ["ORIVIA_001 (STORE_000001)"], index=0)
with b:
    st.date_input("日期", value=date(2026, 3, 5))

st.selectbox("廠商（可先選，方便分段點貨）", ["(全部廠商)", "VENDOR_A"], index=0)
st.divider()

# ============================================================
# Rows
# ============================================================
for it in items:
    st.markdown('<div class="item-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="item-name">{it["name"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="item-meta">單價：{it["price"]:.2f}</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([0.9, 2.1, 0.9, 2.1])

    stock_input_key = f"s_{it['id']}_input"
    stock_value_key = f"s_{it['id']}"
    order_input_key = f"o_{it['id']}_input"
    order_value_key = f"o_{it['id']}"

    # 初始化
    if stock_input_key not in st.session_state:
        st.session_state[stock_input_key] = ""
    if stock_value_key not in st.session_state:
        st.session_state[stock_value_key] = ""

    if order_input_key not in st.session_state:
        st.session_state[order_input_key] = ""
    if order_value_key not in st.session_state:
        st.session_state[order_value_key] = ""

    with c1:
        st.text_input(
            "",
            key=stock_input_key,
            label_visibility="collapsed",
            on_change=sync_clean_input,
            args=(stock_input_key, stock_value_key),
            placeholder="0",
        )

    with c2:
        st.radio(
            "",
            UNIT_OPTIONS,
            horizontal=True,
            key=f"su_{it['id']}",
            label_visibility="collapsed",
        )

    with c3:
        st.text_input(
            "",
            key=order_input_key,
            label_visibility="collapsed",
            on_change=sync_clean_input,
            args=(order_input_key, order_value_key),
            placeholder="0",
        )

    with c4:
        st.radio(
            "",
            UNIT_OPTIONS,
            horizontal=True,
            key=f"ou_{it['id']}",
            label_visibility="collapsed",
        )

    st.markdown("</div>", unsafe_allow_html=True)

# ============================================================
# Debug（可先看值有沒有進來）
# ============================================================
with st.expander("Debug"):
    debug_data = {}
    for it in items:
        debug_data[it["name"]] = {
            "stock_qty": st.session_state.get(f"s_{it['id']}", ""),
            "stock_unit": st.session_state.get(f"su_{it['id']}", ""),
            "order_qty": st.session_state.get(f"o_{it['id']}", ""),
            "order_unit": st.session_state.get(f"ou_{it['id']}", ""),
        }
    st.json(debug_data)
