import streamlit as st

# =========================
# Page config
# =========================
st.set_page_config(page_title="OMS Compact Row Test (Base+Order Unit)", layout="wide")

# =========================
# CSS
# =========================
st.markdown(
    """
<style>
div[data-testid="stTextInput"]{
  max-width:120px;
}
/* 讓整體左右 padding 小一點（手機更省） */
@media (max-width: 640px){
  .block-container{
    padding-left: 8px !important;
    padding-right: 8px !important;
  }
}

/* 卡片更緊湊 */
.item-card{
  padding: 10px 10px;
  border-radius: 12px;
  border: 1px solid rgba(120,120,120,0.18);
  margin-bottom: 10px;
}

.item-name{
  font-size: 18px;
  font-weight: 800;
  line-height: 1.15;
}

.item-meta{
  font-size: 12px;
  opacity: 0.75;
  margin-top: 4px;
  margin-bottom: 8px;
}

/* 輸入框高度縮一點（但不要小到難按） */
div[data-testid="stTextInput"] input{
  height: 34px !important;
  padding: 0 8px !important;
  font-size:10px !important;
}

/* columns 在手機不要換行（避免變四行） */
@media (max-width: 640px){
  div[data-testid="stHorizontalBlock"]{
    flex-wrap: nowrap !important;
    column-gap: 8px !important;
    align-items: center !important;
  }
  div[data-testid="column"]{
    min-width: 0 !important;
  }
}

/* 把 radio 做成小顆 pill（包/箱） */
div[role="radiogroup"]{
  gap: 6px !important;
}
div[role="radiogroup"] label{
  margin: 0 !important;
}
div[role="radiogroup"] label > div{
  padding: 6px 10px !important;
  border-radius: 10px !important;
}

/* radio 本體不要撐太高 */
div[role="radiogroup"] label span{
  font-size: 14px !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Header
# =========================
st.title("OMS Compact Row Test（庫存固定基準 / 叫貨包箱切換）")
st.caption("目標：手機少滑、每品項保持緊湊；庫存=基準單位(固定)，叫貨=包/箱二選一。")
st.divider()

# =========================
# Fake data
# =========================
BASE_UNIT = "KG"          # 庫存基準單位固定
ORDER_UNITS = ["包", "箱"] # 叫貨單位固定二選一

items = [
    {"id": "I001", "name": "測試原料", "price": 10.0},
    {"id": "I002", "name": "魚", "price": 0.0},
    {"id": "I003", "name": "高麗菜", "price": 50.0},
    {"id": "I004", "name": "薯條", "price": 65.0},
]

def ensure_defaults(item_id: str):
    st.session_state.setdefault(f"{item_id}_stock_qty", "0")
    st.session_state.setdefault(f"{item_id}_order_qty", "0")
    st.session_state.setdefault(f"{item_id}_order_unit", ORDER_UNITS[0])  # 預設「包」

# =========================
# Render
# =========================
for it in items:
    ensure_defaults(it["id"])

    st.markdown('<div class="item-card">', unsafe_allow_html=True)

    st.markdown(f'<div class="item-name">{it["name"]}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="item-meta">單價：{it["price"]:.1f} ｜ 庫存基準：{BASE_UNIT}</div>',
        unsafe_allow_html=True,
    )

    # 右側一排：庫存數字 / 叫貨數字 / 叫貨單位(包箱)
    # 比例：讓數字欄位大一點、包箱切換小一點
    c1, c2, c3 = st.columns([0.5, 0.5, 1.0], gap="small")

    with c1:
        st.text_input(
            "庫存",
            key=f"{it['id']}_stock_qty",
            label_visibility="collapsed",
            placeholder="庫存",
        )

    with c2:
        st.text_input(
            "叫貨",
            key=f"{it['id']}_order_qty",
            label_visibility="collapsed",
            placeholder="叫貨",
        )

    with c3:
        st.radio(
            "叫貨單位",
            ORDER_UNITS,
            key=f"{it['id']}_order_unit",
            horizontal=True,
            label_visibility="collapsed",
        )

    st.markdown("</div>", unsafe_allow_html=True)

with st.expander("Debug"):
    st.write(st.session_state)




