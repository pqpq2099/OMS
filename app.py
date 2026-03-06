import streamlit as st

# =========================
# Page config
# =========================
st.set_page_config(page_title="OMS Compact Row Test (Base+Order Unit)", layout="wide")

# =========================
# CSS
# =========================
st.markdown(
    """
<style>
/* ---------- 手機左右 padding 變小，省寬度 ---------- */
@media (max-width: 640px){
  .block-container{
    padding-left: 8px !important;
    padding-right: 8px !important;
  }
}

/* ---------- 卡片更緊湊 ---------- */
.item-card{
  padding: 10px 10px;
  border-radius: 12px;
  border: 1px solid rgba(120,120,120,0.18);
  margin-bottom: 10px;
}
.item-name{
  font-size: 18px;
  font-weight: 800;
  line-height: 1.15;
}
.item-meta{
  font-size: 12px;
  opacity: 0.75;
  margin-top: 4px;
  margin-bottom: 8px;
}

/* ---------- 讓 columns 在手機也不要換行 ---------- */
@media (max-width: 640px){
  div[data-testid="stHorizontalBlock"]{
    flex-wrap: nowrap !important;
    column-gap: 8px !important;
    align-items: center !important;
  }
  div[data-testid="column"]{
    min-width: 0 !important; /* 重要：允許縮到很小 */
  }
}

/* ---------- 輸入框：高度 + 字體 + 取消多餘 padding ---------- */
div[data-testid="stTextInput"]{
  min-width: 0 !important;
}
div[data-testid="stTextInput"] input{
  height: 34px !important;
  padding: 0 8px !important;
  font-size: 15px !important;
  width: 100% !important;
}

/* ---------- Radio pill：做小、不要撐高 ---------- */
div[data-testid="stRadio"]{
  min-width: 0 !important;
}
div[data-testid="stRadio"] div[role="radiogroup"]{
  gap: 6px !important;
  align-items: center !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] label{
  margin: 0 !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] label > div{
  padding: 6px 10px !important;
  border-radius: 10px !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] label span{
  font-size: 14px !important;
}

/* =========================================================
   ✅ 核心：用 :has() 鎖定「庫存/叫貨」那兩個欄位，強制固定寬度
   - 這樣手機才真的會縮，且不會被 Streamlit 的 min-width 撐開
   ========================================================= */
@media (max-width: 640px){
  /* 庫存數字欄位 */
  div[data-testid="column"]:has(input[placeholder="庫存"]){
    flex: 0 0 72px !important;     /* 這個就是你要調的「寬度」 */
    max-width: 72px !important;
  }
  /* 叫貨數字欄位 */
  div[data-testid="column"]:has(input[placeholder="叫貨"]){
    flex: 0 0 72px !important;     /* 這個就是你要調的「寬度」 */
    max-width: 72px !important;
  }
  /* 包/箱 Radio 欄位吃剩下的 */
  div[data-testid="column"]:has(div[data-testid="stRadio"]){
    flex: 1 1 auto !important;
    min-width: 120px !important;   /* 避免被擠到看不到字 */
  }
}
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Header
# =========================
st.title("OMS Compact Row Test（庫存固定基準 / 叫貨包箱切換）")
st.caption("目標：手機少滑、每品項緊湊；庫存=基準單位(固定)，叫貨=包/箱二選一。")
st.divider()

# =========================
# Fake data
# =========================
BASE_UNIT = "KG"
ORDER_UNITS = ["包", "箱"]

items = [
    {"id": "I001", "name": "測試原料", "price": 10.0},
    {"id": "I002", "name": "魚", "price": 0.0},
    {"id": "I003", "name": "高麗菜", "price": 50.0},
    {"id": "I004", "name": "薯條", "price": 65.0},
]

def ensure_defaults(item_id: str):
    st.session_state.setdefault(f"{item_id}_stock_qty", "0")
    st.session_state.setdefault(f"{item_id}_order_qty", "0")
    st.session_state.setdefault(f"{item_id}_order_unit", ORDER_UNITS[0])

# =========================
# Render
# =========================
for it in items:
    ensure_defaults(it["id"])

    st.markdown('<div class="item-card">', unsafe_allow_html=True)

    st.markdown(f'<div class="item-name">{it["name"]}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="item-meta">單價：{it["price"]:.1f} ｜ 庫存基準：{BASE_UNIT}</div>',
        unsafe_allow_html=True,
    )

    # 一排：庫存數字 / 叫貨數字 / 包箱切換
    c1, c2, c3 = st.columns([1, 1, 2], gap="small")

    with c1:
        st.text_input(
            "庫存",
            key=f"{it['id']}_stock_qty",
            label_visibility="collapsed",
            placeholder="庫存",
        )

    with c2:
        st.text_input(
            "叫貨",
            key=f"{it['id']}_order_qty",
            label_visibility="collapsed",
            placeholder="叫貨",
        )

    with c3:
        st.radio(
            "叫貨單位",
            ORDER_UNITS,
            key=f"{it['id']}_order_unit",
            horizontal=True,
            label_visibility="collapsed",
        )

    st.markdown("</div>", unsafe_allow_html=True)

with st.expander("Debug"):
    st.write(st.session_state)
