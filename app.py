import streamlit as st
from datetime import date

st.set_page_config(page_title="OMS Compact Row Template", layout="wide")

# ============================================================
# CSS：像 Excel 一樣的「小格子 + 小間距 + 單位可見」
# ============================================================
st.markdown(
    r"""
<style>
/* 版面不要太寬，避免桌機空得誇張 */
.block-container{
  max-width: 980px !important;
  padding-top: 1rem !important;
  padding-left: 1rem !important;
  padding-right: 1rem !important;
}

/* 卡片樣式（可留可拿掉） */
.orivia-item{
  border: 1px solid rgba(49,51,63,.15);
  border-radius: 12px;
  padding: 12px 12px 10px 12px;
  margin-bottom: 10px;
}
.orivia-name{ font-weight:700; font-size:16px; margin:0 0 6px 0; }
.orivia-meta{ font-size:13px; color:rgba(49,51,63,.65); margin:0 0 10px 0; }

/* -------- 核心：同一行 + 不滑動 + 間距小 -------- */
div[data-testid="stHorizontalBlock"]{
  gap: 6px !important;              /* ✅ 間距小 */
  flex-wrap: nowrap !important;     /* ✅ 同一行 */
  overflow-x: hidden !important;    /* ✅ 不滑動 */
}

/* column 不要撐滿，才能像 Excel 那樣緊貼 */
div[data-testid="column"]{
  flex: 0 0 auto !important;
  width: auto !important;
  padding-left: 0 !important;
  padding-right: 0 !important;
}

/* ✅ 不要用 label 全域 display:none（會害 selectbox 顯示怪）
   我們本來就用 label_visibility="collapsed" 了，所以這裡不動 label
*/

/* -------- number_input：固定窄寬（3位數夠）-------- */
div[data-testid="stNumberInput"]{
  width: 74px !important;
  min-width: 74px !important;
  max-width: 74px !important;
}
div[data-testid="stNumberInput"] input{
  padding: 4px 6px !important;
  font-size: 14px !important;
  text-align: left !important;
}

/* 移除 +/- stepper */
div[data-testid="stNumberInput"] button{ display:none !important; }
div[data-testid="stNumberInput"] div:has(> button){ display:none !important; }

/* -------- selectbox：真正要改的是 baseweb select 本體 -------- */
div[data-testid="stSelectbox"]{
  width: 58px !important;
  min-width: 58px !important;
  max-width: 58px !important;
}

/* baseweb select 容器（這裡才是顯示文字的位置） */
div[data-testid="stSelectbox"] div[data-baseweb="select"]{
  width: 58px !important;
  min-width: 58px !important;
  max-width: 58px !important;
}

/* 顯示區（含文字與箭頭） */
div[data-testid="stSelectbox"] div[role="combobox"]{
  padding: 4px 6px !important;
  font-size: 14px !important;
  min-height: 34px !important;
}

/* 文字不要被裁掉變符號：強制可見 */
div[data-testid="stSelectbox"] span{
  white-space: nowrap !important;
  overflow: visible !important;
  text-overflow: clip !important;
}

/* 箭頭縮小一點（省空間，但還能點） */
div[data-testid="stSelectbox"] svg{
  width: 16px !important;
  height: 16px !important;
}

/* 手機再更緊一點（保證同一行） */
@media (max-width: 768px){
  div[data-testid="stHorizontalBlock"]{ gap: 4px !important; }

  div[data-testid="stNumberInput"]{
    width: 70px !important; min-width: 70px !important; max-width: 70px !important;
  }
  div[data-testid="stSelectbox"],
  div[data-testid="stSelectbox"] div[data-baseweb="select"]{
    width: 54px !important; min-width: 54px !important; max-width: 54px !important;
  }
  div[data-testid="stSelectbox"] div[role="combobox"]{
    padding: 4px 5px !important;
  }
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
        st.number_input(
            "庫",
            min_value=0,
            value=0,
            step=1,
            format="%d",
            key=f"s_{k}",
            label_visibility="collapsed",
        )
    with c2:
        st.selectbox(
            "庫單位",
            it["stock_units"],
            index=0,
            key=f"su_{k}",
            label_visibility="collapsed",
        )
    with c3:
        st.number_input(
            "進",
            min_value=0,
            value=0,
            step=1,
            format="%d",
            key=f"o_{k}",
            label_visibility="collapsed",
        )
    with c4:
        st.selectbox(
            "進單位",
            it["order_units"],
            index=0,
            key=f"ou_{k}",
            label_visibility="collapsed",
        )

    st.markdown("</div>", unsafe_allow_html=True)

with st.expander("Debug"):
    st.write({k: st.session_state.get(k) for k in st.session_state.keys() if "_" in k})
