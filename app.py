import streamlit as st

# =========================
# Page config
# =========================
st.set_page_config(page_title="OMS Compact Row Test (No Overflow)", layout="wide")

# =========================
# CSS
# =========================
st.markdown("""
<style>
@media (max-width: 640px){
  body:before{
    content:"MOBILE MODE";
    position:fixed; top:8px; left:8px;
    z-index:99999;
    background:#ff4b4b; color:white;
    padding:4px 8px; border-radius:6px;
    font-size:12px;
  }
}
</style>
""", unsafe_allow_html=True)
st.markdown(
    """
<style>
/* 讓整體內容不要太散 */
.block-container{
  max-width: 1100px;
  padding-top: 1.2rem;
}

/* --- 卡片 --- */
.item-card{
  padding: 12px 12px;
  border-radius: 12px;
  border: 1px solid rgba(120,120,120,0.2);
  margin-bottom: 14px;
}

/* 左側文字 */
.item-name{
  font-size: 20px;
  font-weight: 800;
  line-height: 1.2;
}
.item-meta{
  font-size: 13px;
  opacity: 0.7;
  margin-top: 6px;
}

/* --- 控件縮小 --- */
div[data-testid="stTextInput"] input{
  height: 38px !important;
  padding: 0 10px !important;
  font-size: 15px !important;
}

div[data-testid="stSelectbox"] div[role="combobox"]{
  height: 38px !important;
  padding: 0 10px !important;
  font-size: 15px !important;
  min-width: 0 !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  white-space: nowrap !important;
}

/* 箭頭別太肥 */
div[data-testid="stSelectbox"] svg{
  width: 16px !important;
  height: 16px !important;
}

/* 右側上下兩排間距縮緊 */
.tight-gap{ margin-top: -6px; }

/* ✅ 手機：避免爆版（最重要） */
@media (max-width: 640px){
  .block-container{
    padding-left: 8px !important;
    padding-right: 8px !important;
  }

  /* ✅ 所有 columns 允許換行，避免 overflow */
  div[data-testid="stHorizontalBlock"]{
    flex-wrap: wrap !important;
    column-gap: 10px !important;
    row-gap: 10px !important;
  }

  /* ✅ column 最小寬度歸零，才能真的縮 */
  div[data-testid="column"]{
    min-width: 0 !important;
  }

  /* ✅ 外層（左品項/右輸入）改成上下堆疊：各佔 100% */
  /* 這個規則會讓任何兩欄 layout 在手機都不硬擠同排，避免爆 */
  div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{
    flex: 1 1 100% !important;
    width: 100% !important;
  }
}
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Header
# =========================
st.title("OMS Compact Row Test（桌機左右 / 手機不爆版）")
st.caption("桌機：左品項 / 右庫存進貨（上數字下單位）；手機：自動改上下堆疊，保證不超出螢幕。")
st.divider()

# =========================
# Fake data
# =========================
UNITS = ["KG", "包", "箱", "袋"]

items = [
    {"id": "I001", "name": "測試原料", "price": 10.0},
    {"id": "I002", "name": "魚", "price": 0.0},
    {"id": "I003", "name": "高麗菜", "price": 50.0},
]

# =========================
# Render rows
# =========================
for item in items:
    st.session_state.setdefault(f"{item['id']}_stock_qty", "0")
    st.session_state.setdefault(f"{item['id']}_stock_unit", "KG")
    st.session_state.setdefault(f"{item['id']}_order_qty", "0")
    st.session_state.setdefault(f"{item['id']}_order_unit", "箱")

    st.markdown('<div class="item-card">', unsafe_allow_html=True)

    # 外層：桌機左右；手機會被 CSS 變成上下堆疊（避免爆版）
    left, right = st.columns([1.25, 2.75], gap="medium")

    with left:
        st.markdown(f'<div class="item-name">{item["name"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="item-meta">單價：{item["price"]:.1f}</div>', unsafe_allow_html=True)

    with right:
        # 右側：上排數字（庫存 / 進貨）
        r1, r2 = st.columns([1, 1], gap="small")
        with r1:
            st.text_input("庫存", key=f"{item['id']}_stock_qty", label_visibility="collapsed")
        with r2:
            st.text_input("進貨", key=f"{item['id']}_order_qty", label_visibility="collapsed")

        # 右側：下排單位（庫存單位 / 進貨單位）
        st.markdown('<div class="tight-gap">', unsafe_allow_html=True)
        u1, u2 = st.columns([1, 1], gap="small")
        with u1:
            st.selectbox("庫存單位", UNITS, key=f"{item['id']}_stock_unit", label_visibility="collapsed")
        with u2:
            st.selectbox("進貨單位", UNITS, key=f"{item['id']}_order_unit", label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

with st.expander("Debug"):
    st.write(dict(st.session_state))

