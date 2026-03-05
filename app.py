import streamlit as st
from datetime import date

st.set_page_config(layout="wide")

# ===== CSS：只負責縮小格子 =====
st.markdown("""
<style>

.block-container{
    max-width: 980px;
}

/* 數字欄 */
div[data-testid="stTextInput"]{
    width:70px !important;
}
div[data-testid="stTextInput"] input{
    padding:4px !important;
}

/* 下拉 */
div[data-testid="stSelectbox"]{
    width:80px !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"]{
    min-height:32px !important;
}

/* item */
.item{
    border:1px solid rgba(0,0,0,0.08);
    border-radius:10px;
    padding:10px;
    margin-bottom:10px;
}

</style>
""", unsafe_allow_html=True)

items = [
    {"id":1,"name":"薯條","price":50},
    {"id":2,"name":"測試原料","price":10},
]

units = ["KG","包","箱"]

# header
a,b = st.columns([2,1])
with a:
    st.selectbox("分店",["ORIVIA_001"])
with b:
    st.date_input("日期",date.today())

st.divider()

# 表頭
h = st.columns([3.5,1,1.2,1,1.2])
h[0].write("品項名稱")
h[1].write("庫存")
h[2].write("單位")
h[3].write("進貨")
h[4].write("單位")

# rows
for item in items:

    with st.container():

        c = st.columns([3.5,1,1.2,1,1.2])

        with c[0]:
            st.markdown(f"""
            **{item["name"]}**  
            單價 {item["price"]}
            """)

        with c[1]:
            st.text_input("",key=f"s_{item['id']}")

        with c[2]:
            st.selectbox("",units,key=f"su_{item['id']}")

        with c[3]:
            st.text_input("",key=f"o_{item['id']}")

        with c[4]:
            st.selectbox("",units,key=f"ou_{item['id']}")
