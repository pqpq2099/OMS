import streamlit as st
from datetime import date

st.set_page_config(page_title="OMS Compact (No :has)", layout="wide")

# ============================================================
# CSS：不使用 :has()，只縮 stTextInput / stRadio
# ============================================================
st.markdown("""
<style>
.block-container{ max-width: 980px; padding: 16px 16px 32px; }

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
  width: 62px !important;      /* 三位數寬度 */
  min-width: 62px !important;
  max-width: 62px !important;
}
div[data-testid="stTextInput"] input{
  padding: 2px 4px !important;
  font-size: 13px !important;
  line-height: 1.1 !important;
}

/* ========= 單位：radio 水平很省 ========= */
div[data-testid="stRadio"]{
  width: 150px !important;     /* 3 個短選項剛好 */
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

/* 卡片（只是好看，不影響功能） */
.item-card{
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
}
.item-name{ font-size: 16px; font-weight: 700; margin: 0 0 4px 0; }
.item-meta{ font-size: 13px; color: #666; margin: 0 0 8px 0; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# Demo data
# ============================================================
items = [
    {"id":"1","name":"測試原料","price":10.0},
    {"id":"2","name":"魚","price":0.0},
    {"id":"3","name":"高麗菜","price":50.0},
]

# ============================================================
# Header（這裡不用縮）
# ============================================================
a, b = st.columns([2, 1])
with a:
    st.selectbox("分店", ["ORIVIA_001 (STORE_000001)"], index=0)
with b:
    st.date_input("日期", value=date(2026, 3, 5))
st.selectbox("廠商（可先選，方便分段點貨）", ["(全部廠商)", "VENDOR_A"], index=0)
st.divider()

# ============================================================
# Helpers：只允許數字（空字串允許，避免輸入卡住）
# ============================================================
def sanitize_int(s: str) -> str:
    s = (s or "").strip()
    if s == "":
        return ""
    return "".join(ch for ch in s if ch.isdigit())[:4]  # 最多 4 位（你要三位就改 [:3]）

UNIT_OPTIONS = ["KG", "包", "箱"]

# ============================================================
# Rows：手機也能一行（庫數字 + 庫單位 + 進數字 + 進單位）
# 單位用 radio 水平，避免 selectbox 最小寬度卡死
# ============================================================
for it in items:
    st.markdown('<div class="item-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="item-name">{it["name"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="item-meta">單價：{it["price"]:.2f}</div>', unsafe_allow_html=True)

    # 一行 4 區：數字、單位、數字、單位
    c1, c2, c3, c4 = st.columns([0.9, 2.1, 0.9, 2.1])

    with c1:
        k = f"s_{it['id']}"
        v = st.text_input("", value=st.session_state.get(k, ""), key=k, label_visibility="collapsed")
        st.session_state[k] = sanitize_int(v)

    with c2:
        st.radio("", UNIT_OPTIONS, horizontal=True, key=f"su_{it['id']}", label_visibility="collapsed")

    with c3:
        k = f"o_{it['id']}"
        v = st.text_input("", value=st.session_state.get(k, ""), key=k, label_visibility="collapsed")
        st.session_state[k] = sanitize_int(v)

    with c4:
        st.radio("", UNIT_OPTIONS, horizontal=True, key=f"ou_{it['id']}", label_visibility="collapsed")

    st.markdown("</div>", unsafe_allow_html=True)
