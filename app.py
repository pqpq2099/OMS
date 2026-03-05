import streamlit as st

st.set_page_config(layout="wide")

st.title("OMS Compact Row Test")

UNITS = ["KG","包","箱"]

items = [
    {"id":"1","name":"測試原料","price":10},
    {"id":"2","name":"魚","price":0},
]

for item in items:

    st.markdown("---")

    # 第一行：品項 + 庫存 + 進貨
    c1,c2,c3 = st.columns([3,1,1])

    with c1:
        st.markdown(f"""
        **{item["name"]}**  
        單價：{item["price"]}
        """)

    with c2:
        st.text_input("庫存", key=f"{item['id']}_stock", label_visibility="collapsed")

    with c3:
        st.text_input("進貨", key=f"{item['id']}_order", label_visibility="collapsed")

    # 第二行：單位
    c4,c5,c6 = st.columns([3,1,1])

    with c5:
        st.selectbox("庫存單位", UNITS, key=f"{item['id']}_su", label_visibility="collapsed")

    with c6:
        st.selectbox("進貨單位", UNITS, key=f"{item['id']}_ou", label_visibility="collapsed")
