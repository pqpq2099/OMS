import streamlit as st
from datetime import date

st.set_page_config(page_title="OMS Row Grid (Hard Lock)", layout="wide")

# ============================================================
# CSS：1) 只作用在 .orivia-row  2) 手機永遠同一行 3) stepper 永久移除
# ============================================================
st.markdown(
    r"""
<style>
.block-container{
  max-width: 980px !important;
  padding: 1rem !important;
}

/* 卡片 */
.orivia-item{
  border: 1px solid rgba(49,51,63,.15);
  border-radius: 12px;
  padding: 12px 12px 10px 12px;
  margin-bottom: 10px;
}
.orivia-name{ font-weight:700; font-size:16px; margin:0 0 6px 0; }
.orivia-meta{ font-size:13px; color:rgba(49,51,63,.65); margin:0 0 10px 0; }

/* ✅ 這是我們自建的 grid 容器：手機也不會拆行 */
.orivia-rowgrid{
  display: grid;
  grid-template-columns: 92px 78px 92px 78px; /* 你要的格子感 */
  gap: 8px;
  align-items: center;
  width: fit-content;          /* 不要被撐滿 */
  max-width: 100%;
}

/* 讓每個 widget 外層不要撐爆 grid cell */
.orivia-rowgrid > div{
  min-width: 0;
}

/* number_input / selectbox：填滿各自 cell */
.orivia-rowgrid div[data-testid="stNumberInput"],
.orivia-rowgrid div[data-testid="stSelectbox"]{
  width: 100% !important;
}

/* number input 視覺 */
.orivia-rowgrid div[data-testid="stNumberInput"] input{
  padding: 6px 8px !important;
  font-size: 15px !important;
}

/* select 視覺 + 文字可見 */
.orivia-rowgrid div[data-testid="stSelectbox"] div[data-baseweb="select"]{
  width: 100% !important;
}
.orivia-rowgrid div[data-testid="stSelectbox"] div[role="combobox"]{
  padding: 6px 8px !important;
  font-size: 15px !important;
  min-height: 36px !important;
}
.orivia-rowgrid div[data-testid="stSelectbox"] span{
  white-space: nowrap !important;
  overflow: visible !important;
  text-overflow: clip !important;
}
.orivia-rowgrid div[data-testid="stSelectbox"] svg{
  width: 16px !important;
  height: 16px !important;
}

/* ============================================================
   ✅ Stepper 永久移除（新版舊版都抓）
   ============================================================ */

/* 1) 舊版：stNumberInput 內 button */
div[data-testid="stNumberInput"] button{ display:none !important; }

/* 2) 新版：baseweb input 的 stepper（常見 data-baseweb="input"） */
div[data-testid="stNumberInput"] [data-baseweb="input"] button{ display:none !important; }

/* 3) 有些版本用 role="spinbutton" 的旁邊控制區 */
div[data-testid="stNumberInput"] div[role="spinbutton"] + div{ display:none !important; }

/* 4) 最保險：任何 number input 裡的 svg icon 按鈕都隱藏 */
div[data-testid="stNumberInput"] svg{ display:none !important; }
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# Demo data
# ============================================================
items = [
    {"id": "1", "name": "測試原料", "unit_price": 10.0, "stock_units": ["KG", "包"], "order_units": ["箱", "包"]},
    {"id": "2", "name": "魚", "unit_price": 0.0, "stock_units": ["包"], "order_units": ["包"]},
    {"id": "3", "name": "高麗菜", "unit_price": 50.0, "stock_units": ["包", "KG"], "order_units": ["包", "箱"]},
]

# Header（正常，不受影響）
top1, top2 = st.columns([2, 1])
with top1:
    st.selectbox("分店", ["ORIVIA_001 (STORE_000001)"], index=0)
with top2:
    st.date_input("日期", value=date(2026, 3, 5))
st.selectbox("廠商（可先選，方便分段點貨）", ["(全部廠商)", "VENDOR_A"], index=0)
st.divider()

# ============================================================
# Rows：不用 st.columns(4)，改「HTML grid + 4 個 container」
# ============================================================
for it in items:
    k = it["id"]

    st.markdown('<div class="orivia-item">', unsafe_allow_html=True)
    st.markdown(f'<div class="orivia-name">{it["name"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="orivia-meta">單價：{it["unit_price"]:.2f}</div>', unsafe_allow_html=True)

    st.markdown('<div class="orivia-rowgrid">', unsafe_allow_html=True)

    a = st.container()
    b = st.container()
    c = st.container()
    d = st.container()

    with a:
        st.number_input("庫", min_value=0, value=0, step=1, format="%d",
                        key=f"s_{k}", label_visibility="collapsed")
    with b:
        st.selectbox("庫單位", it["stock_units"], index=0,
                     key=f"su_{k}", label_visibility="collapsed")
    with c:
        st.number_input("進", min_value=0, value=0, step=1, format="%d",
                        key=f"o_{k}", label_visibility="collapsed")
    with d:
        st.selectbox("進單位", it["order_units"], index=0,
                     key=f"ou_{k}", label_visibility="collapsed")

    st.markdown("</div>", unsafe_allow_html=True)  # close rowgrid
    st.markdown("</div>", unsafe_allow_html=True)  # close item
