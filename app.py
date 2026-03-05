import streamlit as st
from datetime import date

st.set_page_config(page_title="OMS UI Width Test", layout="wide")

st.markdown("""
<style>
/* 版面寬度 */
.block-container{ max-width: 980px; padding: 1rem 1rem 2rem; }

/* =========================================
   ✅ 核心：抓「有 number_input + selectbox」的 columns row
   直接鎖 Streamlit 自己的 stHorizontalBlock
========================================= */

/* 只針對：同一排裡同時出現 number_input 與 selectbox 的水平區塊 */
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stNumberInput"]):has(div[data-testid="stSelectbox"]){
  display:flex !important;
  flex-wrap:nowrap !important;   /* 不換行（手機也不換） */
  gap:6px !important;            /* 間距縮小 */
  align-items:center !important;
}

/* column 基礎：不要被撐爆 */
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stNumberInput"]):has(div[data-testid="stSelectbox"])
  > div[data-testid="column"]{
  padding:0 !important;
  margin:0 !important;
  min-width:0 !important;
}

/* 數字欄位 column：固定寬度（可吃 3 位數） */
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stNumberInput"]):has(div[data-testid="stSelectbox"])
  > div[data-testid="column"]:has(div[data-testid="stNumberInput"]){
  flex:0 0 92px !important;
  width:92px !important;
  max-width:92px !important;
}

/* 單位欄位 column：固定窄寬（1~2 字 + 箭頭） */
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stNumberInput"]):has(div[data-testid="stSelectbox"])
  > div[data-testid="column"]:has(div[data-testid="stSelectbox"]){
  flex:0 0 74px !important;
  width:74px !important;
  max-width:74px !important;
}

/* widget 吃滿自己的 column */
div[data-testid="stNumberInput"], div[data-testid="stSelectbox"]{ width:100% !important; }

/* number input：縮 padding */
div[data-testid="stNumberInput"] input{
  padding:6px 8px !important;
  font-size:15px !important;
}

/* selectbox：縮 padding + 讓文字不要被吃掉 */
div[data-testid="stSelectbox"] div[role="combobox"]{
  padding:6px 8px !important;
  min-height:36px !important;
  font-size:15px !important;
}
div[data-testid="stSelectbox"] span{
  white-space:nowrap !important;
  overflow:visible !important;
  text-overflow:clip !important;
}

/* ✅ Stepper 永久移除 */
div[data-testid="stNumberInput"] button{ display:none !important; }
div[data-testid="stNumberInput"] svg{ display:none !important; }
div[data-testid="stNumberInput"] [data-baseweb="input"] button{ display:none !important; }

</style>
""", unsafe_allow_html=True)


# -----------------------
# 測試資料
# -----------------------
items = [
    {"id":"1","name":"測試原料","price":10.0,"stock_units":["KG","包"],"order_units":["箱","包"]},
    {"id":"2","name":"魚","price":0.0,"stock_units":["包"],"order_units":["包"]},
    {"id":"3","name":"高麗菜","price":50.0,"stock_units":["包","KG"],"order_units":["包","箱"]},
]

# -----------------------
# Header（跟你的 OMS 類似）
# -----------------------
a,b = st.columns([2,1])
with a:
    st.selectbox("分店", ["ORIVIA_001 (STORE_000001)"], index=0)
with b:
    st.date_input("日期", value=date(2026,3,5))
st.selectbox("廠商（可先選，方便分段點貨）", ["(全部廠商)", "VENDOR_A"], index=0)

st.divider()

# -----------------------
# 列表：每個品項一排四格
# -----------------------
for it in items:
    st.markdown(f"**{it['name']}**")
    st.caption(f"單價：{it['price']:.2f}")

    c1,c2,c3,c4 = st.columns(4)
    with c1:
        st.number_input("庫", min_value=0.0, value=0.0, step=1.0, format="%.0f",
                        key=f"s_{it['id']}", label_visibility="collapsed")
    with c2:
        st.selectbox("庫單位", it["stock_units"], index=0,
                     key=f"su_{it['id']}", label_visibility="collapsed")
    with c3:
        st.number_input("進", min_value=0.0, value=0.0, step=1.0, format="%.0f",
                        key=f"o_{it['id']}", label_visibility="collapsed")
    with c4:
        st.selectbox("進單位", it["order_units"], index=0,
                     key=f"ou_{it['id']}", label_visibility="collapsed")

    st.markdown("---")
