import streamlit as st
from datetime import date

st.set_page_config(page_title="OMS Compact Selectbox Template (Fit Mobile)", layout="wide")

st.markdown("""
<style>
.block-container{ max-width: 980px; padding: 16px 16px 32px; }

.item-card{
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 10px;
}
.item-name{ font-weight: 700; font-size: 16px; margin: 0 0 4px 0; }
.item-meta{ color: #666; font-size: 13px; margin: 0 0 8px 0; }

.head{
  font-weight: 700;
  font-size: 14px;
  color: #222;
  margin: 6px 0 6px 0;
}

/* ====== 核心：用 grid 固定欄寬 ====== */
.row-grid{
  display: grid;
  grid-template-columns: 1fr 72px 84px 72px 84px; /* 品名區 + 4格 */
  column-gap: 6px;
  align-items: center;
}

/* ====== 手機：整排縮放，避免超出螢幕 ======
   這裡用 scale 把 row-grid 縮到螢幕內（不換行、不溢出）
*/
@media (max-width: 520px){
  .row-grid{
    transform: scale(0.88);
    transform-origin: left top;
  }
}

/* ====== 讓 Streamlit 元件不要亂撐寬 ====== */
.row-grid > div{ min-width: 0 !important; }

/* 數字格 */
div[data-testid="stTextInput"]{
  width: 72px !important;
  min-width: 72px !important;
  max-width: 72px !important;
}
div[data-testid="stTextInput"] input{
  padding: 4px 6px !important;
  font-size: 14px !important;
  line-height: 1.1 !important;
}

/* 下拉格 */
div[data-testid="stSelectbox"]{
  width: 84px !important;
  min-width: 84px !important;
  max-width: 84px !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"]{
  width: 84px !important;
  min-width: 84px !important;
  max-width: 84px !important;
}
div[data-testid="stSelectbox"] *{ font-size: 14px !important; }
div[data-testid="stSelectbox"] svg{ width: 14px !important; height: 14px !important; }
</style>
""", unsafe_allow_html=True)

items = [
    {"id":"1","name":"薯條", "price":50.0, "stock_unit":"包", "order_unit":"包"},
    {"id":"2","name":"測試原料", "price":10.0, "stock_unit":"KG", "order_unit":"箱"},
    {"id":"3","name":"魚", "price":0.0, "stock_unit":"包", "order_unit":"包"},
]
UNITS = ["KG", "包", "箱"]

def sanitize_num(s: str) -> str:
    s = (s or "").strip()
    if s == "":
        return ""
    out, dot = [], False
    for ch in s:
        if ch.isdigit():
            out.append(ch)
        elif ch == "." and not dot:
            out.append("."); dot = True
    cleaned = "".join(out)
    if "." in cleaned:
        a, b = cleaned.split(".", 1)
        cleaned = a + "." + b[:1]
    return cleaned[:6]

def on_clean(k: str):
    st.session_state[k] = sanitize_num(st.session_state.get(k, ""))

# Header
c1, c2 = st.columns([2, 1])
with c1:
    st.selectbox("分店", ["ORIVIA_001"], index=0)
with c2:
    st.date_input("日期", value=date(2026, 3, 5))
st.selectbox("廠商（可先選，方便分段點貨）", ["(全部廠商)", "VENDOR_A"], index=0)
st.divider()

# 表頭
h = st.columns([3.6, 0.9, 1.0, 0.9, 1.0])
h[0].markdown('<div class="head">品項名稱</div>', unsafe_allow_html=True)
h[1].markdown('<div class="head">庫存</div>', unsafe_allow_html=True)
h[2].markdown('<div class="head">單位</div>', unsafe_allow_html=True)
h[3].markdown('<div class="head">進貨</div>', unsafe_allow_html=True)
h[4].markdown('<div class="head">單位</div>', unsafe_allow_html=True)

# Rows
for it in items:
    st.markdown('<div class="item-card">', unsafe_allow_html=True)

    # 這邊刻意讓「品名欄」跟輸入同一排，最貼近你 Excel 圖2
    st.markdown('<div class="row-grid">', unsafe_allow_html=True)

    # 1) 品名 + 單價（放在同一格）
    st.markdown(
        f'<div><div class="item-name">{it["name"]}</div>'
        f'<div class="item-meta">單價 {it["price"]:.0f}</div></div>',
        unsafe_allow_html=True
    )

    # 2) 庫存數字
    k1 = f"stock_qty_{it['id']}"
    if k1 not in st.session_state: st.session_state[k1] = ""
    st.text_input("", key=k1, label_visibility="collapsed", on_change=on_clean, args=(k1,), placeholder="0")

    # 3) 庫存單位
    st.selectbox("", UNITS, index=UNITS.index(it["stock_unit"]), key=f"stock_unit_{it['id']}", label_visibility="collapsed")

    # 4) 進貨數字
    k2 = f"order_qty_{it['id']}"
    if k2 not in st.session_state: st.session_state[k2] = ""
    st.text_input("", key=k2, label_visibility="collapsed", on_change=on_clean, args=(k2,), placeholder="0")

    # 5) 進貨單位
    st.selectbox("", UNITS, index=UNITS.index(it["order_unit"]), key=f"order_unit_{it['id']}", label_visibility="collapsed")

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with st.expander("Debug"):
    st.json({k: v for k, v in st.session_state.items() if "qty_" in k or "unit_" in k})
