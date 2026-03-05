import streamlit as st
from datetime import date

st.set_page_config(page_title="OMS Grid Compact Template", layout="wide")

# ============================================================
# CSS：用 Grid 強制四格寬度與間距（關鍵）
# ============================================================
st.markdown(
    r"""
<style>
.block-container{
  max-width: 980px !important;
  padding: 1rem !important;
}

/* 卡片（可留可拿掉） */
.orivia-item{
  border: 1px solid rgba(49,51,63,.15);
  border-radius: 12px;
  padding: 12px 12px 10px 12px;
  margin-bottom: 10px;
}
.orivia-name{ font-weight:700; font-size:16px; margin:0 0 6px 0; }
.orivia-meta{ font-size:13px; color:rgba(49,51,63,.65); margin:0 0 10px 0; }

/* ✅ 核心：把「輸入那一排」強制改成 Grid */
div[data-testid="stHorizontalBlock"]{
  display: grid !important;
  grid-template-columns: 72px 64px 72px 64px !important; /* 3位數 / KG */
  column-gap: 6px !important;  /* 間隔小 */
  align-items: center !important;
}

/* columns 本身不要再撐 */
div[data-testid="column"]{
  width: auto !important;
  padding: 0 !important;
  margin: 0 !important;
  min-width: 0 !important;
}

/* ---------- number_input：固定寬度 + 移除 stepper ---------- */
div[data-testid="stNumberInput"]{
  width: 100% !important;      /* 跟著 grid 欄寬走 */
}
div[data-testid="stNumberInput"] input{
  padding: 4px 6px !important;
  font-size: 14px !important;
}
div[data-testid="stNumberInput"] button{ display:none !important; }
div[data-testid="stNumberInput"] div:has(> button){ display:none !important; }

/* ---------- selectbox：讓「文字一定顯示」 ---------- */
div[data-testid="stSelectbox"]{
  width: 100% !important;      /* 跟著 grid 欄寬走 */
}
div[data-testid="stSelectbox"] div[data-baseweb="select"]{
  width: 100% !important;
}
div[data-testid="stSelectbox"] div[role="combobox"]{
  padding: 4px 4px !important; /* ✅ 省空間給文字 */
  font-size: 14px !important;
  min-height: 34px !important;
}
/* ✅ 讓文字不被裁成 K */
div[data-testid="stSelectbox"] span{
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: clip !important;
}

/* 手機再縮一點，保證同一行 */
@media (max-width: 768px){
  div[data-testid="stHorizontalBlock"]{
    grid-template-columns: 68px 60px 68px 60px !important;
    column-gap: 4px !important;
  }
  div[data-testid="stNumberInput"] input{ padding: 4px 5px !important; }
  div[data-testid="stSelectbox"] div[role="combobox"]{ padding: 4px 3px !important; }
}
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

# ============================================================
# Header
# ============================================================
top1, top2 = st.columns([2, 1])
with top1:
    st.selectbox("分店", ["ORIVIA_001 (STORE_000001)"], index=0)
with top2:
    st.date_input("日期", value=date(2026, 3, 5))
st.selectbox("廠商（可先選，方便分段點貨）", ["(全部廠商)", "VENDOR_A"], index=0)
st.divider()

# ============================================================
# Rows
# ============================================================
for it in items:
    k = it["id"]
    st.markdown('<div class="orivia-item">', unsafe_allow_html=True)
    st.markdown(f'<div class="orivia-name">{it["name"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="orivia-meta">單價：{it["unit_price"]:.2f}</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.number_input("庫", min_value=0, value=0, step=1, format="%d",
                        key=f"s_{k}", label_visibility="collapsed")
    with c2:
        st.selectbox("庫單位", it["stock_units"], index=0,
                     key=f"su_{k}", label_visibility="collapsed")
    with c3:
        st.number_input("進", min_value=0, value=0, step=1, format="%d",
                        key=f"o_{k}", label_visibility="collapsed")
    with c4:
        st.selectbox("進單位", it["order_units"], index=0,
                     key=f"ou_{k}", label_visibility="collapsed")

    st.markdown("</div>", unsafe_allow_html=True)
