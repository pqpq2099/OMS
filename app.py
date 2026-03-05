import streamlit as st

st.set_page_config(page_title="OMS Compact Row Test v2", layout="wide")

# =========================
# CSS：強制 columns 在手機也維持「同一排」、縮小間距、隱藏 +/- stepper
# =========================
st.markdown("""
<style>
/* container padding 縮小一點 */
.block-container { padding-top: 1rem; padding-bottom: 2rem; }

/* 隱藏 number_input 的 +/- stepper（兩種 selector 都放） */
button[aria-label="Increment"], button[aria-label="Decrement"] { display: none !important; }
[data-testid="stNumberInputStepUp"], [data-testid="stNumberInputStepDown"] { display: none !important; }

/* ====== 核心：強制「columns 橫排、不換行」 ======
   Streamlit columns 外層通常是 stHorizontalBlock（flex）
   手機預設會改成直排/換行，我們強制回 row + nowrap
*/
div[data-testid="stHorizontalBlock"]{
  display: flex !important;
  flex-direction: row !important;
  flex-wrap: nowrap !important;
  gap: 10px !important;         /* 欄位間距 */
  align-items: flex-start !important;
}

/* columns 每欄不要被拉到很寬，讓它能縮 */
div[data-testid="stHorizontalBlock"] > div{
  flex: 0 0 auto !important;
  min-width: 0 !important;
}

/* 讓 input/select 吃滿欄位寬 */
div[data-testid="stNumberInput"], div[data-testid="stSelectbox"] { width: 100% !important; }
div[data-testid="stNumberInput"] input { width: 100% !important; }
div[data-testid="stSelectbox"] [data-baseweb="select"] { width: 100% !important; }

/* 下拉選單 padding 微縮，讓單位不要被擠沒 */
div[data-testid="stSelectbox"] [data-baseweb="select"] > div{
  padding-left: 8px !important;
  padding-right: 30px !important;
}

/* 數字欄位 padding 微縮 */
div[data-testid="stNumberInput"] input{
  padding-left: 8px !important;
  padding-right: 8px !important;
}

/* 手機再縮一點（避免爆寬） */
@media (max-width: 640px){
  .block-container { padding-left: 0.8rem; padding-right: 0.8rem; }
  div[data-testid="stHorizontalBlock"]{ gap: 8px !important; }
}
</style>
""", unsafe_allow_html=True)

st.title("OMS Compact Row Test v2（只測 UI）")
st.caption("目標：桌機一排、手機也一排；庫存(數字+單位) / 進貨(數字+單位)，不出現 +/-。")
st.divider()

ITEMS = [
    ("測試原料", 10.0, ["KG", "包", "箱"], ["箱", "包", "KG"]),
    ("魚", 0.0, ["包", "KG", "箱"], ["包", "箱", "KG"]),
    ("高麗菜", 50.0, ["包", "KG"], ["包", "箱"]),
]

def row(i, name, price, stock_units, order_units):
    st.markdown(f"### {name}")
    st.caption(f"單價：{price:.1f}")

    # ✅ 這裡是你要的「四格同一行」
    # 數字框：三位數就夠 -> 欄位比例給大一點；單位 -> 小一點
    c1, c2, c3, c4 = st.columns([1.2, 0.9, 1.2, 0.9], gap="small")

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
