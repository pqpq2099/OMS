import streamlit as st
from datetime import date

st.set_page_config(page_title="OMS Compact Selectbox Template", layout="wide")

# ============================================================
# CSS：不靠 :has()，直接縮 stTextInput / stSelectbox + 縮間距 + 強制同排
# ============================================================
st.markdown("""
<style>
/* 容器 */
.block-container{ max-width: 980px; padding: 16px 16px 32px; }

/* columns 一律同排、不換行、縮gap（手機也不換行） */
div[data-testid="stHorizontalBlock"]{
  flex-wrap: nowrap !important;
  gap: 6px !important;
}

/* column 不要撐爆 */
div[data-testid="column"]{
  padding: 0 !important;
  margin: 0 !important;
  min-width: 0 !important;
}

/* ===== 數字格（text_input） ===== */
div[data-testid="stTextInput"]{
  width: 72px !important;        /* 你要三位數 OK；想更小改 64/68 */
  min-width: 72px !important;
  max-width: 72px !important;
}
div[data-testid="stTextInput"] input{
  padding: 4px 6px !important;
  font-size: 14px !important;
  line-height: 1.1 !important;
}

/* ===== 下拉格（selectbox） ===== */
div[data-testid="stSelectbox"]{
  width: 84px !important;        /* 單位格寬度：夠顯示 KG/包/箱 */
  min-width: 84px !important;
  max-width: 84px !important;
}

/* BaseWeb select 內部（Streamlit selectbox 其實是 BaseWeb） */
div[data-testid="stSelectbox"] div[data-baseweb="select"]{
  width: 84px !important;
  min-width: 84px !important;
  max-width: 84px !important;
}

/* select 文字與padding縮小 */
div[data-testid="stSelectbox"] *{
  font-size: 14px !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
  padding-top: 2px !important;
  padding-bottom: 2px !important;
}

/* 讓下拉箭頭區不要吃掉太多寬度 */
div[data-testid="stSelectbox"] svg{
  width: 14px !important;
  height: 14px !important;
}

/* item card（只是分隔好看） */
.item-card{
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 10px;
}
.item-name{ font-weight: 700; font-size: 16px; margin: 0 0 4px 0; }
.item-meta{ color: #666; font-size: 13px; margin: 0 0 8px 0; }

/* 標題列（像Excel表頭） */
.head{
  font-weight: 700;
  font-size: 14px;
  color: #222;
  margin: 6px 0 6px 0;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# Demo data
# ============================================================
items = [
    {"id":"1","name":"薯條","price":50.0, "stock_unit":"包", "order_unit":"包"},
    {"id":"2","name":"測試原料","price":10.0, "stock_unit":"KG", "order_unit":"箱"},
    {"id":"3","name":"魚","price":0.0, "stock_unit":"包", "order_unit":"包"},
]
UNITS = ["KG", "包", "箱"]

def sanitize_num(s: str) -> str:
    """允許整數+小數1位（可輸入 60.0 / 2.5 / 1.5），其他字元過濾"""
    s = (s or "").strip()
    if s == "":
        return ""
    out = []
    dot = False
    for ch in s:
        if ch.isdigit():
            out.append(ch)
        elif ch == "." and not dot:
            out.append(".")
            dot = True
    cleaned = "".join(out)
    # 控制小數最多1位
    if "." in cleaned:
        a, b = cleaned.split(".", 1)
        cleaned = a + "." + b[:1]
    return cleaned[:6]  # 長度上限避免太長

def on_clean(input_key: str):
    st.session_state[input_key] = sanitize_num(st.session_state.get(input_key, ""))

# ============================================================
# Header
# ============================================================
c1, c2 = st.columns([2, 1])
with c1:
    st.selectbox("分店", ["ORIVIA_001"], index=0)
with c2:
    st.date_input("日期", value=date(2026, 3, 5))
st.selectbox("廠商（可先選，方便分段點貨）", ["(全部廠商)", "VENDOR_A"], index=0)
st.divider()

# ============================================================
# Excel-like header row
# ============================================================
h1, h2, h3, h4, h5 = st.columns([3.6, 0.9, 1.0, 0.9, 1.0])
with h1: st.markdown('<div class="head">品項名稱</div>', unsafe_allow_html=True)
with h2: st.markdown('<div class="head">庫存</div>', unsafe_allow_html=True)
with h3: st.markdown('<div class="head">單位</div>', unsafe_allow_html=True)
with h4: st.markdown('<div class="head">進貨</div>', unsafe_allow_html=True)
with h5: st.markdown('<div class="head">單位</div>', unsafe_allow_html=True)

# ============================================================
# Rows
# ============================================================
for it in items:
    st.markdown('<div class="item-card">', unsafe_allow_html=True)
    # 你要像Excel一樣也可以把品名放同排；這裡先保留品名+單價在上方
    st.markdown(f'<div class="item-name">{it["name"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="item-meta">單價：{it["price"]:.2f}</div>', unsafe_allow_html=True)

    a, b, c, d, e = st.columns([3.6, 0.9, 1.0, 0.9, 1.0])

    with a:
        st.write("")  # 保留空間，讓欄位對齊（不放元件）

    with b:
        k = f"stock_qty_{it['id']}"
        if k not in st.session_state:
            st.session_state[k] = ""
        st.text_input("", key=k, label_visibility="collapsed", on_change=on_clean, args=(k,), placeholder="0")

    with c:
        st.selectbox("", UNITS, index=UNITS.index(it["stock_unit"]), key=f"stock_unit_{it['id']}", label_visibility="collapsed")

    with d:
        k = f"order_qty_{it['id']}"
        if k not in st.session_state:
            st.session_state[k] = ""
        st.text_input("", key=k, label_visibility="collapsed", on_change=on_clean, args=(k,), placeholder="0")

    with e:
        st.selectbox("", UNITS, index=UNITS.index(it["order_unit"]), key=f"order_unit_{it['id']}", label_visibility="collapsed")

    st.markdown("</div>", unsafe_allow_html=True)

with st.expander("Debug"):
    st.json({k: v for k, v in st.session_state.items() if "qty_" in k or "unit_" in k})
