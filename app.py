import streamlit as st
from datetime import date

st.set_page_config(page_title="OMS Test", layout="wide")

# ============================================================
# CSS：控制排版 + 移除 stepper
# ============================================================

st.markdown("""
<style>

/* 整體寬度 */
.block-container{
    max-width: 980px;
}

/* 品項卡片 */
.orivia-item{
    border:1px solid rgba(0,0,0,0.08);
    border-radius:10px;
    padding:12px;
    margin-bottom:12px;
}

/* 名稱 */
.orivia-name{
    font-size:16px;
    font-weight:700;
}

/* 單價 */
.orivia-meta{
    font-size:13px;
    color:#666;
    margin-bottom:8px;
}

/* ======================================================
   關鍵：讓 columns 在手機也維持同一行
====================================================== */

.orivia-row div[data-testid="stHorizontalBlock"]{
    display:flex !important;
    flex-wrap:nowrap !important;
    gap:8px !important;
}

/* column 不要撐滿 */
.orivia-row div[data-testid="column"]{
    padding:0 !important;
    min-width:0 !important;
}

/* 數字欄位 */
.orivia-row div[data-testid="column"]:has(div[data-testid="stNumberInput"]){
    flex:0 0 90px !important;
    max-width:90px !important;
}

/* 單位欄位 */
.orivia-row div[data-testid="column"]:has(div[data-testid="stSelectbox"]){
    flex:0 0 80px !important;
    max-width:80px !important;
}

/* input 寬度填滿 */
.orivia-row div[data-testid="stNumberInput"],
.orivia-row div[data-testid="stSelectbox"]{
    width:100% !important;
}

/* 移除 number_input stepper */
div[data-testid="stNumberInput"] button{
    display:none !important;
}

div[data-testid="stNumberInput"] svg{
    display:none !important;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# 測試資料
# ============================================================

items = [
    {"id":"1","name":"測試原料","price":10,"stock_units":["KG","包"],"order_units":["箱","包"]},
    {"id":"2","name":"魚","price":0,"stock_units":["包"],"order_units":["包"]},
    {"id":"3","name":"高麗菜","price":50,"stock_units":["包","KG"],"order_units":["包","箱"]},
]


# ============================================================
# Header
# ============================================================

c1,c2 = st.columns([2,1])

with c1:
    st.selectbox("分店",["ORIVIA_001 (STORE_000001)"])

with c2:
    st.date_input("日期",date(2026,3,5))

st.selectbox("廠商（可先選，方便分段點貨）",["全部廠商","A廠商","B廠商"])

st.divider()


# ============================================================
# 品項列
# ============================================================

for it in items:

    st.markdown('<div class="orivia-item">',unsafe_allow_html=True)

    st.markdown(f'<div class="orivia-name">{it["name"]}</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="orivia-meta">單價：{it["price"]:.2f}</div>',unsafe_allow_html=True)

    st.markdown('<div class="orivia-row">',unsafe_allow_html=True)

    col1,col2,col3,col4 = st.columns(4)

    with col1:
        st.number_input(
            "庫存",
            min_value=0,
            step=1,
            value=0,
            key=f"s_{it['id']}",
            label_visibility="collapsed"
        )

    with col2:
        st.selectbox(
            "庫單位",
            it["stock_units"],
            key=f"su_{it['id']}",
            label_visibility="collapsed"
        )

    with col3:
        st.number_input(
            "進貨",
            min_value=0,
            step=1,
            value=0,
            key=f"o_{it['id']}",
            label_visibility="collapsed"
        )

    with col4:
        st.selectbox(
            "進單位",
            it["order_units"],
            key=f"ou_{it['id']}",
            label_visibility="collapsed"
        )

    st.markdown('</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)
