import streamlit as st

# =========================
# Page config
# =========================
st.set_page_config(page_title="OMS Compact Row Test (Units Below)", layout="wide")

# =========================
# CSS
# =========================
st.markdown(
    """
<style>

/* --- 手機避免左右 padding 吃寬度 --- */
@media (max-width: 640px){
  .block-container{
    padding-left: 6px !important;
    padding-right: 6px !important;
  }

  /* columns 保持同一排（上排：庫存/進貨；下排：單位/單位） */
  div[data-testid="stHorizontalBlock"]{
    flex-wrap: nowrap !important;
    column-gap: 10px !important;   /* ✅ 間距稍微打開 */
  }

  /* column 可以縮小（避免撐爆） */
  div[data-testid="column"]{
    min-width: 0 !important;
  }
}

/* --- 輸入框樣式 --- */
div[data-testid="stTextInput"] input{
  height: 44px !important;
  padding: 0 10px !important;
  font-size: 16px !important;
}

/* --- 下拉選單（combobox） --- */
div[data-testid="stSelectbox"] div[role="combobox"]{
  height: 44px !important;
  padding: 0 10px !important;
  font-size: 16px !important;
  min-width: 0 !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  white-space: nowrap !important;
}

/* 下拉箭頭不要太肥 */
div[data-testid="stSelectbox"] svg{
  width: 18px !important;
  height: 18px !important;
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

/* 讓「數字列」和「單位列」之間更緊湊 */
.row-tight{
  margin-top: -6px;
}

</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Header
# =========================
st.title("OMS Compact Row Test（下拉在下面）")
st.caption("目標：上排庫存/進貨數字；下排各自單位下拉。手機也不爆版。")
st.divider()

# =========================
# 假資料
# =========================
UNITS = ["KG", "包", "箱", "袋"]

items = [
    {"id": "I001", "name": "測試原料", "price": 10.0},
    {"id": "I002", "name": "魚", "price": 0.0},
    {"id": "I003", "name": "高麗菜", "price": 50.0},
]

# =========================
# Render rows
# =========================
for item in items:
    st.session_state.setdefault(f"{item['id']}_stock_qty", "0")
    st.session_state.setdefault(f"{item['id']}_stock_unit", "KG")
    st.session_state.setdefault(f"{item['id']}_order_qty", "0")
    st.session_state.setdefault(f"{item['id']}_order_unit", "箱")

    st.markdown('<div class="item-card">', unsafe_allow_html=True)

    st.markdown(f'<div class="item-name">{item["name"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="item-meta">單價：{item["price"]:.1f}</div>', unsafe_allow_html=True)

    # -------- 上排：庫存數字 / 進貨數字 --------
    # ✅ 兩格就好：這樣手機一定能同一排
    n1, n2 = st.columns([1, 1], gap="small")

    with n1:
        st.text_input(
            "庫存",
            key=f"{item['id']}_stock_qty",
            label_visibility="collapsed",
        )

    with n2:
        st.text_input(
            "進貨",
            key=f"{item['id']}_order_qty",
            label_visibility="collapsed",
        )

    # -------- 下排：庫存單位 / 進貨單位 --------
    # ✅ 下拉放下面（各自對應）
    st.markdown('<div class="row-tight">', unsafe_allow_html=True)
    u1, u2 = st.columns([1, 1], gap="small")

    with u1:
        st.selectbox(
            "庫存單位",
            UNITS,
            key=f"{item['id']}_stock_unit",
            label_visibility="collapsed",
        )

    with u2:
        st.selectbox(
            "進貨單位",
            UNITS,
            key=f"{item['id']}_order_unit",
            label_visibility="collapsed",
        )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# Debug
# =========================
with st.expander("Debug"):
    st.write(dict(st.session_state))
