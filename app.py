import streamlit as st
from datetime import date

st.set_page_config(page_title="OMS Mobile Compact", layout="wide")

# ============================================================
# CSS（重點：縮寬度 + 縮間距）
# ============================================================

st.markdown("""
<style>

/* 整體頁面寬度 */
.block-container{
    max-width:900px;
    padding-top:1rem;
}

/* 行內間距縮小 */
div[data-testid="stHorizontalBlock"]{
    gap:6px !important;
    flex-wrap:nowrap !important;
}

/* column 不撐滿 */
div[data-testid="column"]{
    flex:0 0 auto !important;
    width:auto !important;
    padding:0 !important;
}

/* number_input 寬度（可輸入3~4位數） */
div[data-testid="stNumberInput"]{
    width:80px !important;
}

/* input padding */
div[data-testid="stNumberInput"] input{
    padding:4px 6px !important;
    font-size:14px !important;
}

/* 移除 +/- */
div[data-testid="stNumberInput"] button{
    display:none !important;
}

/* selectbox 寬度 */
div[data-testid="stSelectbox"]{
    width:60px !important;
}

/* selectbox 文字 */
div[data-testid="stSelectbox"] div[role="combobox"]{
    padding:4px 6px !important;
    font-size:14px !important;
}

/* label 不佔位 */
label{
    display:none !important;
}

</style>
""", unsafe_allow_html=True)

# ============================================================
# Demo data
# ============================================================

items = [
    {"id":"1","name":"測試原料","unit_price":10},
    {"id":"2","name":"魚","unit_price":0},
    {"id":"3","name":"高麗菜","unit_price":50}
]

# ============================================================
# Header
# ============================================================

top1,top2 = st.columns([2,1])

with top1:
    st.selectbox("分店",["ORIVIA_001"])

with top2:
    st.date_input("日期",date(2026,3,5))

st.selectbox("廠商（可先選，方便分段點貨）",["全部廠商"])

st.divider()

# ============================================================
# Rows
# ============================================================

for item in items:

    st.markdown(f"**{item['name']}**")
    st.caption(f"單價 {item['unit_price']}")

    c1,c2,c3,c4 = st.columns(4)

    with c1:
        st.number_input("",key=f"s_{item['id']}",value=0,step=1)

    with c2:
        st.selectbox("",["KG","包"],key=f"su_{item['id']}")

    with c3:
        st.number_input("",key=f"o_{item['id']}",value=0,step=1)

    with c4:
        st.selectbox("",["箱","包"],key=f"ou_{item['id']}")

    st.divider()
