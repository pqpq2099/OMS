import streamlit as st
from datetime import date

st.set_page_config(page_title="OMS UI", layout="wide")

# ===============================
# CSS
# ===============================
st.markdown("""
<style>

.block-container{
  max-width: 980px;
  padding: 1rem 1rem 2rem;
}

/* 只抓有 number_input + selectbox 的 row */
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stNumberInput"]):has(div[data-testid="stSelectbox"]){
  display:flex !important;
  flex-wrap:nowrap !important;
  gap:2px !important;
  align-items:center !important;
  width:fit-content !important;
}

/* column 基礎 */
div[data-testid="column"]{
  padding:0 !important;
  margin:0 !important;
  min-width:0 !important;
}

/* 數字欄位 */
div[data-testid="column"]:has(div[data-testid="stNumberInput"]){
  flex:0 0 60px !important;
  width:60px !important;
}

/* 單位欄位 */
div[data-testid="column"]:has(div[data-testid="stSelectbox"]){
  flex:0 0 46px !important;
  width:46px !important;
}

/* widget */
div[data-testid="stNumberInput"], div[data-testid="stSelectbox"]{
  width:100% !important;
  min-width:0 !important;
}

/* number input */
div[data-testid="stNumberInput"] input{
  padding:2px 4px !important;
  font-size:13px !important;
}

/* selectbox */
div[data-testid="stSelectbox"] div[data-baseweb="select"]{
  min-width:0 !important;
}

div[data-testid="stSelectbox"] div[role="combobox"]{
  padding:2px !important;
  min-height:28px !important;
  font-size:13px !important;
}

/* 移除 stepper */
div[data-testid="stNumberInput"] button{
  display:none !important;
}

</style>
""", unsafe_allow_html=True)


# ===============================
# Demo data
# ===============================
items = [
    {"id":"1","name":"測試原料","price":10,"stock_units":["KG","包"],"order_units":["箱","包"]},
    {"id":"2","name":"魚","price":0,"stock_units":["包"],"order_units":["包"]},
    {"id":"3","name":"高麗菜","price":50,"stock_units":["包","KG"],"order_units":["包","箱"]},
]


# ===============================
# Header
# ===============================
c1,c2 = st.columns([2,1])

with c1:
    st.selectbox("分店",["ORIVIA_001"])

with c2:
    st.date_input("日期",date(2026,3,5))

st.selectbox("廠商",["全部廠商"])

st.divider()


# ===============================
# Items
# ===============================
for item in items:

    st.markdown(f"**{item['name']}**")
    st.caption(f"單價 {item['price']}")

    col1,col2,col3,col4 = st.columns(4)

    with col1:
        st.number_input("",value=0,step=1,key=f"s_{item['id']}")

    with col2:
        st.selectbox("",item["stock_units"],key=f"su_{item['id']}")

    with col3:
        st.number_input("",value=0,step=1,key=f"o_{item['id']}")

    with col4:
        st.selectbox("",item["order_units"],key=f"ou_{item['id']}")

    st.divider()
