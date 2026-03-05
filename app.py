import streamlit as st

st.set_page_config(page_title="OMS Compact Row Test v7", layout="wide")

st.markdown("""
<style>

/* 卡片 */
.item-card{
    padding:14px;
    border-radius:14px;
    border:1px solid rgba(120,120,120,0.2);
    margin-bottom:16px;
}

/* grid layout */
.item-grid{
    display:grid;
    grid-template-columns: 2fr 1fr 1fr;
    grid-template-rows:auto auto auto;
    column-gap:10px;
    row-gap:6px;
}

/* 手機版 */
@media (max-width:640px){

    .item-grid{
        grid-template-columns: 1fr 1fr;
    }

    .item-name{
        grid-column:1 / -1;
    }

}

/* 控件大小 */
div[data-testid="stTextInput"] input{
    height:40px !important;
    font-size:16px !important;
}

div[data-testid="stSelectbox"] > div{
    height:40px !important;
}

</style>
""", unsafe_allow_html=True)

st.title("OMS Compact Row Test v7")

UNITS=["KG","包","箱"]

items=[
    {"id":"1","name":"測試原料","price":10},
    {"id":"2","name":"魚","price":0},
]

for item in items:

    st.markdown('<div class="item-card">',unsafe_allow_html=True)

    st.markdown(f"""
    <div class="item-name">
    {item["name"]}<br>
    <small>單價 {item["price"]}</small>
    </div>
    """,unsafe_allow_html=True)

    c1,c2=st.columns(2)

    with c1:
        st.text_input("庫存",key=f"{item['id']}_s",label_visibility="collapsed")
        st.selectbox("單位",UNITS,key=f"{item['id']}_su",label_visibility="collapsed")

    with c2:
        st.text_input("進貨",key=f"{item['id']}_o",label_visibility="collapsed")
        st.selectbox("單位",UNITS,key=f"{item['id']}_ou",label_visibility="collapsed")

    st.markdown("</div>",unsafe_allow_html=True)
