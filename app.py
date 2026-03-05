import streamlit as st
from datetime import date

st.set_page_config(page_title="OMS Row Grid (Scoped)", layout="wide")

# ============================================================
# CSS：只鎖定「品項那一排」(.orivia-row) 套 Grid
# ============================================================
st.markdown(
    r"""
<style>
.block-container{
  max-width: 980px !important;
  padding: 1rem !important;
}

/* 卡片外框 */
.orivia-item{
  border: 1px solid rgba(49,51,63,.15);
  border-radius: 12px;
  padding: 12px 12px 10px 12px;
  margin-bottom: 10px;
}
.orivia-name{ font-weight:700; font-size:16px; margin:0 0 6px 0; }
.orivia-meta{ font-size:13px; color:rgba(49,51,63,.65); margin:0 0 10px 0; }

/* ============================================================
   ✅ 關鍵：只對 .orivia-row 裡的 stHorizontalBlock 變成 Grid
   ============================================================ */
.orivia-row div[data-testid="stHorizontalBlock"]{
  display: grid !important;
  /* 用 clamp 讓桌機/手機同一套規則，自動縮放但不失控 */
  grid-template-columns:
    clamp(84px, 20vw, 96px)   /* number */
    clamp(70px, 16vw, 86px)   /* unit   */
    clamp(84px, 20vw, 96px)   /* number */
    clamp(70px, 16vw, 86px)   /* unit   */
    !important;

  column-gap: 8px !important;
  align-items: center !important;

  /* 不滑動、一定同一行 */
  overflow-x: hidden !important;
}

/* .orivia-row 內的 columns 不要撐開 */
.orivia-row div[data-testid="column"]{
  width: auto !important;
  padding: 0 !important;
  margin: 0 !important;
  min-width: 0 !important;
}

/* number_input：吃滿格子寬 */
.orivia-row div[data-testid="stNumberInput"]{ width:100% !important; }
.orivia-row div[data-testid="stNumberInput"] input{
  padding: 6px 8px !important;
  font-size: 15px !important;
}

/* 移除 +/- */
.orivia-row div[data-testid="stNumberInput"] button{ display:none !important; }
.orivia-row div[data-testid="stNumberInput"] div:has(> button){ display:none !important; }

/* selectbox：吃滿格子寬，文字一定顯示 */
.orivia-row div[data-testid="stSelectbox"]{ width:100% !important; }
.orivia-row div[data-testid="stSelectbox"] div[data-baseweb="select"]{ width:100% !important; }
.orivia-row div[data-testid="stSelectbox"] div[role="combobox"]{
  padding: 6px 8px !important;
  font-size: 15px !important;
  min-height: 36px !important;
}

/* 文字不要被裁成 K */
.orivia-row div[data-testid="stSelectbox"] span{
  white-space: nowrap !important;
  overflow: visible !important;
  text-overflow: clip !important;
}

/* 箭頭縮小一點，省空間但保留可點 */
.orivia-row div[data-testid="stSelectbox"] svg{
  width: 16px !important;
  height: 16px !important;
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
# Header（這裡不會被 Grid 影響了）
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

    # ✅ 只包住這一排：Grid 只作用於這裡
    st.markdown('<div class="orivia-row">', unsafe_allow_html=True)

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

    st.markdown("</div>", unsafe_allow_html=True)  # close .orivia-row
    st.markdown("</div>", unsafe_allow_html=True)  # close .orivia-item
