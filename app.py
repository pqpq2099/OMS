import streamlit as st

# =========================
# Page config
# =========================
st.set_page_config(
    page_title="OMS Compact Row Test",
    layout="wide"
)

# =========================
# CSS
# =========================
st.markdown("""
<style>

/* ---------- 整體左右 padding ---------- */
@media (max-width:640px){
.block-container{
    padding-left:10px;
    padding-right:10px;
}
}

/* ---------- 卡片 ---------- */
.item-card{
padding:10px;
border-radius:12px;
border:1px solid rgba(120,120,120,0.18);
margin-bottom:12px;
}

.item-name{
font-size:18px;
font-weight:700;
}

.item-meta{
font-size:12px;
opacity:0.75;
margin-bottom:8px;
}

/* ---------- 輸入框 ---------- */
div[data-testid="stTextInput"] input{
height:34px;
font-size:15px;
padding:0 8px;
}

/* 限制輸入框最大寬度 */
div[data-testid="stTextInput"]{
max-width:80px;
}

/* ---------- column 間距 ---------- */
div[data-testid="stHorizontalBlock"]{
column-gap:6px !important;
}

/* ---------- radio pill ---------- */
div[role="radiogroup"]{
gap:6px !important;
}

div[role="radiogroup"] label > div{
padding:6px 10px !important;
border-radius:10px;
}

div[role="radiogroup"] label span{
font-size:14px;
}

</style>
""", unsafe_allow_html=True)


# =========================
# Header
# =========================
st.title("OMS Compact Row Test（庫存固定基準 / 叫貨包箱切換）")

st.caption("目標：手機少滑，每品項保持緊湊")

st.divider()


# =========================
# 假資料
# =========================
BASE_UNIT = "KG"

ORDER_UNITS = ["包","箱"]

items = [
{"id":"I001","name":"測試原料","price":10.0},
{"id":"I002","name":"魚","price":0.0},
{"id":"I003","name":"高麗菜","price":50.0},
{"id":"I004","name":"薯條","price":65.0},
]


def ensure_defaults(i):

    st.session_state.setdefault(f"{i}_stock","0")

    st.session_state.setdefault(f"{i}_order","0")

    st.session_state.setdefault(f"{i}_unit","包")


# =========================
# Render
# =========================
for it in items:

    ensure_defaults(it["id"])

    st.markdown('<div class="item-card">', unsafe_allow_html=True)

    st.markdown(
        f'<div class="item-name">{it["name"]}</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="item-meta">{it["price"]} / {BASE_UNIT}</div>',
        unsafe_allow_html=True
    )

    # 比例控制寬度
    c1,c2,c3 = st.columns([0.35,0.35,1.3], gap="small")

    with c1:
        st.text_input(
            "庫存",
            key=f"{it['id']}_stock",
            label_visibility="collapsed",
            placeholder="庫"
        )

    with c2:
        st.text_input(
            "叫貨",
            key=f"{it['id']}_order",
            label_visibility="collapsed",
            placeholder="叫"
        )

    with c3:
        st.radio(
            "單位",
            ORDER_UNITS,
            key=f"{it['id']}_unit",
            horizontal=True,
            label_visibility="collapsed"
        )

    st.markdown("</div>", unsafe_allow_html=True)


# =========================
# Debug
# =========================
with st.expander("Debug"):
    st.write(st.session_state)
