import streamlit as st

# =========================
# Page config
# =========================
st.set_page_config(page_title="OMS Compact Row Test (Dropdown Below)", layout="wide")

# =========================
# CSS (scoped)
# =========================
st.markdown(
    """
<style>
/* ========= Global container ========= */
.block-container{
  max-width: 1100px;
  padding-top: 1.2rem;
  padding-bottom: 2rem;
}

/* ========= Card ========= */
.item-card{
  padding: 14px 12px;
  border-radius: 14px;
  border: 1px solid rgba(120,120,120,0.18);
  margin: 12px 0 16px 0;
}

.item-name{
  font-size: 20px;
  font-weight: 800;
  line-height: 1.2;
  margin-bottom: 2px;
}
.item-meta{
  font-size: 13px;
  opacity: 0.65;
  margin-bottom: 10px;
}

/* ========= Widget sizing ========= */
.ui-scope div[data-testid="stTextInput"] input{
  height: 40px !important;
  padding: 0 10px !important;
  font-size: 16px !important;
}
.ui-scope div[data-testid="stSelectbox"] > div{
  min-height: 40px !important;
}
.ui-scope div[data-testid="stSelectbox"] div[role="combobox"]{
  min-height: 40px !important;
  padding-top: 0px !important;
  padding-bottom: 0px !important;
}

/* ========= Row layout control (SCOPED) ========= */
/* 桌機：固定不換行，欄位緊湊 */
.ui-scope .row-top div[data-testid="stHorizontalBlock"],
.ui-scope .row-unit div[data-testid="stHorizontalBlock"]{
  flex-wrap: nowrap !important;
  column-gap: 10px !important;
}
.ui-scope .row-top div[data-testid="column"],
.ui-scope .row-unit div[data-testid="column"]{
  min-width: 0 !important;
}

/* ========= Mobile ========= */
@media (max-width: 640px){

  /* 手機把左右 padding 壓小，避免吃掉寬度 */
  .block-container{
    padding-left: 8px !important;
    padding-right: 8px !important;
  }

  /* 讓「上排(品項+庫存+進貨)」可以換行，但用我們指定規則排成兩欄 */
  .ui-scope .row-top div[data-testid="stHorizontalBlock"]{
    flex-wrap: wrap !important;
    column-gap: 8px !important;
    row-gap: 8px !important;
  }

  /* row-top: 第1欄(品項)滿寬；第2/3欄(庫存/進貨)各半寬 */
  .ui-scope .row-top div[data-testid="column"]:nth-child(1){
    flex: 1 1 100% !important;
    width: 100% !important;
  }
  .ui-scope .row-top div[data-testid="column"]:nth-child(2),
  .ui-scope .row-top div[data-testid="column"]:nth-child(3){
    flex: 1 1 calc(50% - 6px) !important;
    width: calc(50% - 6px) !important;
  }

  /* 下排(單位)：直接兩欄並排，不需要左邊留白 */
  .ui-scope .row-unit div[data-testid="stHorizontalBlock"]{
    flex-wrap: wrap !important;
    column-gap: 8px !important;
    row-gap: 8px !important;
  }
  /* row-unit: 隱藏「桌機用的左側留白欄」(第1欄) */
  .ui-scope .row-unit div[data-testid="column"]:nth-child(1){
    display: none !important;
  }
  /* row-unit: 第2/3欄各半寬 */
  .ui-scope .row-unit div[data-testid="column"]:nth-child(2),
  .ui-scope .row-unit div[data-testid="column"]:nth-child(3){
    flex: 1 1 calc(50% - 6px) !important;
    width: calc(50% - 6px) !important;
  }
}
</style>
    """,
    unsafe_allow_html=True
)

# =========================
# Header
# =========================
st.title("OMS Compact Row Test（下拉在下面）")
st.caption("桌機：品項左、庫存/進貨右；手機：不溢出、兩欄並排；下拉選單在數字下面。")
st.divider()

# =========================
# Fake data
# =========================
UNITS = ["KG", "包", "箱", "袋"]
items = [
    {"id": "I001", "name": "測試原料", "price": 10.0},
    {"id": "I002", "name": "魚", "price": 0.0},
    {"id": "I003", "name": "高麗菜", "price": 50.0},
]

def ensure_state(key: str, default):
    if key not in st.session_state:
        st.session_state[key] = default

# =========================
# Render
# =========================
for item in items:
    iid = item["id"]

    ensure_state(f"{iid}_stock_qty", "0")
    ensure_state(f"{iid}_stock_unit", "KG")
    ensure_state(f"{iid}_order_qty", "0")
    ensure_state(f"{iid}_order_unit", "箱")

    st.markdown('<div class="item-card ui-scope">', unsafe_allow_html=True)

    # --- Top row: item(left) + stock qty(right) + order qty(right)
    st.markdown('<div class="row-top">', unsafe_allow_html=True)
    c_item, c_stock_qty, c_order_qty = st.columns([2.6, 1.2, 1.2], gap="small")

    with c_item:
        st.markdown(f'<div class="item-name">{item["name"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="item-meta">單價：{item["price"]:.1f}</div>', unsafe_allow_html=True)

    with c_stock_qty:
        st.text_input("庫存", key=f"{iid}_stock_qty", label_visibility="collapsed")

    with c_order_qty:
        st.text_input("進貨", key=f"{iid}_order_qty", label_visibility="collapsed")

    st.markdown("</div>", unsafe_allow_html=True)

    # --- Unit row: (desktop align right with spacer) + stock unit + order unit
    st.markdown('<div class="row-unit">', unsafe_allow_html=True)
    s0, c_stock_unit, c_order_unit = st.columns([2.6, 1.2, 1.2], gap="small")
    with s0:
        st.empty()  # spacer for desktop alignment
    with c_stock_unit:
        st.selectbox("庫存單位", UNITS, key=f"{iid}_stock_unit", label_visibility="collapsed")
    with c_order_unit:
        st.selectbox("進貨單位", UNITS, key=f"{iid}_order_unit", label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

with st.expander("Debug"):
    st.write(st.session_state)
