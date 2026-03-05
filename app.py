import streamlit as st

st.set_page_config(page_title="OMS Compact Row Test v3", layout="wide")

st.markdown("""
<style>
.block-container { padding-top: 1rem; padding-bottom: 2rem; }

/* 隱藏 number_input +/- stepper */
button[aria-label="Increment"], button[aria-label="Decrement"] { display: none !important; }
[data-testid="stNumberInputStepUp"], [data-testid="stNumberInputStepDown"] { display: none !important; }

/* ✅ 核心：強制 columns 手機也橫排 + 不換行 */
div[data-testid="stHorizontalBlock"]{
  display: flex !important;
  flex-direction: row !important;
  flex-wrap: nowrap !important;
  gap: 8px !important;
  align-items: center !important;
}
div[data-testid="stHorizontalBlock"] > div{
  flex: 0 0 auto !important;
  min-width: 0 !important;
}

/* 讓 input / select 吃滿欄位寬 */
div[data-testid="stNumberInput"], div[data-testid="stSelectbox"] { width: 100% !important; }
div[data-testid="stNumberInput"] input { width: 100% !important; }
div[data-testid="stSelectbox"] [data-baseweb="select"] { width: 100% !important; }

/* ✅ 修正：select 內容一定要看得到 */
div[data-testid="stSelectbox"] [data-baseweb="select"] > div{
  min-height: 40px !important;
  display: flex !important;
  align-items: center !important;
  padding-left: 10px !important;
  padding-right: 36px !important;   /* 右側箭頭區保留 */
  overflow: visible !important;
}

/* ✅ 修正：選到的文字（value）不准被吃掉/透明 */
div[data-testid="stSelectbox"] [data-baseweb="select"] span{
  opacity: 1 !important;
  visibility: visible !important;
  display: inline-block !important;
  white-space: nowrap !important;
}

/* 數字欄位 padding */
div[data-testid="stNumberInput"] input{
  min-height: 40px !important;
  padding-left: 10px !important;
  padding-right: 10px !important;
}

/* 手機微調 */
@media (max-width: 640px){
  .block-container { padding-left: 0.8rem; padding-right: 0.8rem; }
  div[data-testid="stHorizontalBlock"]{ gap: 6px !important; }
}
</style>
""", unsafe_allow_html=True)

st.title("OMS Compact Row Test v3（只測 UI）")
st.caption("目標：桌機一排、手機也一排；庫存(數字+單位) / 進貨(數字+單位)，單位必顯示。")
st.divider()

ITEMS = [
    ("測試原料", 10.0, ["KG", "包", "箱"], ["箱", "包", "KG"]),
    ("魚", 0.0, ["包", "KG", "箱"], ["包", "箱", "KG"]),
    ("高麗菜", 50.0, ["包", "KG"], ["包", "箱"]),
]

def row(i, name, price, stock_units, order_units):
    st.markdown(f"### {name}")
    st.caption(f"單價：{price:.1f}")

    # ✅ 四格同一行：數字稍大、單位稍小（但要看得到）
    c1, c2, c3, c4 = st.columns([1.35, 0.85, 1.35, 0.85], gap="small")

    with c1:
        st.number_input("庫存", min_value=0.0, value=0.0, step=0.0, format="%.1f",
                        key=f"s_qty_{i}", label_visibility="collapsed")
    with c2:
        st.selectbox("庫存單位", stock_units, index=0,
                     key=f"s_unit_{i}", label_visibility="collapsed")
    with c3:
        st.number_input("進貨", min_value=0.0, value=0.0, step=0.0, format="%.1f",
                        key=f"o_qty_{i}", label_visibility="collapsed")
    with c4:
        st.selectbox("進貨單位", order_units, index=0,
                     key=f"o_unit_{i}", label_visibility="collapsed")

    st.markdown("<hr/>", unsafe_allow_html=True)

for i, (n, p, su, ou) in enumerate(ITEMS):
    row(i, n, p, su, ou)

with st.expander("Debug"):
    st.json({k: v for k, v in st.session_state.items()})
