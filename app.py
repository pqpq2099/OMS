import streamlit as st

# =========================
# Page config
# =========================
st.set_page_config(page_title="OMS Compact Row Test", layout="wide")

# =========================
# CSS
# =========================
st.markdown("""
<style>

/* --- 手機避免左右 padding 吃寬度 --- */
@media (max-width: 640px){
  .block-container{
    padding-left: 6px !important;
    padding-right: 6px !important;
  }

  /* columns 保持同一排 */
  div[data-testid="stHorizontalBlock"]{
    flex-wrap: nowrap !important;
    column-gap: 6px !important;
  }

  /* column 可以縮小 */
  div[data-testid="column"]{
    min-width: 0 !important;
  }
}

/* --- 輸入框樣式 --- */
div[data-testid="stTextInput"] input{
  height: 44px !important;
  padding: 0 8px !important;
  font-size: 16px !important;
}

/* --- 下拉選單 --- */
div[data-testid="stSelectbox"] > div{
  height: 44px !important;
}

/* --- 卡片樣式 --- */
.item-card{
  padding: 14px 12px;
  border-radius: 12px;
  border: 1px solid rgba(120,120,120,0.2);
  margin-bottom: 16px;
}

.item-name{
  font-size: 22px;
  font-weight: 800;
}

.item-meta{
  font-size: 14px;
  opacity: 0.7;
  margin-bottom: 10px;
}

</style>
""", unsafe_allow_html=True)

# =========================
# Header
# =========================
st.title("OMS Compact Row Test")
st.caption("測試：手機同一排顯示（庫存 + 單位 / 進貨 + 單位）")

st.divider()

# =========================
# 假資料
# =========================
UNITS = ["KG","包","箱","袋"]

items = [
    {"id":"I001","name":"測試原料","price":10.0},
    {"id":"I002","name":"魚","price":0.0},
    {"id":"I003","name":"高麗菜","price":50.0},
]

# =========================
# Render rows
# =========================
for item in items:

    st.session_state.setdefault(f"{item['id']}_stock_qty","0")
    st.session_state.setdefault(f"{item['id']}_stock_unit","KG")
    st.session_state.setdefault(f"{item['id']}_order_qty","0")
    st.session_state.setdefault(f"{item['id']}_order_unit","箱")

    st.markdown('<div class="item-card">',unsafe_allow_html=True)

    st.markdown(f'<div class="item-name">{item["name"]}</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="item-meta">單價：{item["price"]:.1f}</div>',unsafe_allow_html=True)

    # 欄位比例（手機最穩）
    c1,c2,c3,c4 = st.columns([1.3,0.7,1.3,0.7],gap="small")

    with c1:
        st.text_input("庫存",
            key=f"{item['id']}_stock_qty",
            label_visibility="collapsed")

    with c2:
        st.selectbox("庫存單位",
            UNITS,
            key=f"{item['id']}_stock_unit",
            label_visibility="collapsed")

    with c3:
        st.text_input("進貨",
            key=f"{item['id']}_order_qty",
            label_visibility="collapsed")

    with c4:
        st.selectbox("進貨單位",
            UNITS,
            key=f"{item['id']}_order_unit",
            label_visibility="collapsed")

    st.markdown("</div>",unsafe_allow_html=True)

# =========================
# Debug
# =========================
with st.expander("Debug"):
    st.write(st.session_state)
