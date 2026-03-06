import streamlit as st

# ============================================================
# [0] Page config
# ============================================================
st.set_page_config(page_title="OMS Compact Row Test", layout="wide")

# ============================================================
# [1] Tuning knobs (你只改這裡)
# ============================================================
# 欄位間距
DESKTOP_GAP_PX = 10
MOBILE_GAP_PX = 8

# 右側區塊內：兩個數字欄的比例（越小越窄）
# 注意：這是「比例」，不是 px。Streamlit 用比例分配寬度
NUM_RATIO = 1.0
NUM_RATIO_2 = 1.0
TOGGLE_RATIO = 2.2

# 卡片內 padding
CARD_PAD_Y = 10
CARD_PAD_X = 10

# ============================================================
# [2] CSS (不要用 f-string，避免 {} 爆掉)
# ============================================================
st.markdown(
    """
<style>
/* ------------------------------
   全局：讓 columns 在小螢幕不要自己換行
   ------------------------------ */
@media (max-width: 640px){
  .block-container{
    padding-left: 8px !important;
    padding-right: 8px !important;
  }
  /* columns 的外層：不要 wrap */
  div[data-testid="stHorizontalBlock"]{
    flex-wrap: nowrap !important;
    column-gap: var(--mobile-gap) !important;
    align-items: center !important;
  }
  div[data-testid="column"]{
    min-width: 0 !important;
  }
}

/* 桌機 gap */
div[data-testid="stHorizontalBlock"]{
  column-gap: var(--desktop-gap) !important;
}

/* ------------------------------
   讓 TextInput/Radio 可以被「壓窄」
   主要是把 min-width 拿掉，不然手機永遠撐爆
   ------------------------------ */
div[data-testid="stTextInput"]{
  min-width: 0 !important;
  width: 100% !important;
}
div[data-testid="stTextInput"] input{
  min-width: 0 !important;
  width: 100% !important;
  height: 36px !important;
  padding: 0 10px !important;
  font-size: 15px !important;
}

/* radio group 不要撐爆 */
div[role="radiogroup"]{
  min-width: 0 !important;
  width: 100% !important;
  gap: 8px !important;
}
div[role="radiogroup"] label{
  margin: 0 !important;
}
div[role="radiogroup"] label > div{
  padding: 6px 10px !important;
  border-radius: 10px !important;
}
div[role="radiogroup"] label span{
  font-size: 14px !important;
}

/* ------------------------------
   卡片樣式
   ------------------------------ */
.oms-card{
  padding: var(--card-pad-y) var(--card-pad-x);
  border-radius: 12px;
  border: 1px solid rgba(120,120,120,0.18);
  margin-bottom: 10px;
}
.oms-name{
  font-size: 18px;
  font-weight: 800;
  line-height: 1.15;
}
.oms-meta{
  font-size: 12px;
  opacity: 0.75;
  margin-top: 4px;
  margin-bottom: 8px;
}

/* ------------------------------
   右側兩個數字欄：同一排、靠近一點
   （這裡是讓兩個輸入欄看起來更緊）
   ------------------------------ */
.oms-right-tight div[data-testid="stHorizontalBlock"]{
  column-gap: 8px !important;
}
@media (max-width: 640px){
  .oms-right-tight div[data-testid="stHorizontalBlock"]{
    column-gap: 8px !important;
  }
}
</style>
""",
    unsafe_allow_html=True,
)

# 把 tuning knobs 丟成 CSS 變數（用 set_option 方式做不到，只能塞到 :root）
st.markdown(
    f"""
<style>
:root {{
  --desktop-gap: {DESKTOP_GAP_PX}px;
  --mobile-gap: {MOBILE_GAP_PX}px;
  --card-pad-y: {CARD_PAD_Y}px;
  --card-pad-x: {CARD_PAD_X}px;
}}
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# [3] Header
# ============================================================
st.title("OMS Compact Row Test（庫存固定基準 / 叫貨包箱切換）")
st.caption("目標：手機不要變直排、不超出螢幕；左品項、右庫存/叫貨，包/箱用切換。")
st.divider()

# ============================================================
# [4] Fake data
# ============================================================
BASE_UNIT = "KG"               # 庫存基準（固定，不下拉）
ORDER_UNITS = ["包", "箱"]      # 叫貨單位（先固定二選一，未來可改成動態）

items = [
    {"id": "I001", "name": "測試原料", "price": 10.0},
    {"id": "I002", "name": "魚", "price": 0.0},
    {"id": "I003", "name": "高麗菜", "price": 50.0},
    {"id": "I004", "name": "薯條", "price": 65.0},
    {"id": "I005", "name": "雞塊", "price": 162.8},
]

def ensure_defaults(item_id: str):
    st.session_state.setdefault(f"{item_id}_stock_qty", "0")
    st.session_state.setdefault(f"{item_id}_order_qty", "0")
    st.session_state.setdefault(f"{item_id}_order_unit", ORDER_UNITS[0])  # 預設包

# ============================================================
# [5] Render
# ============================================================
for it in items:
    ensure_defaults(it["id"])

    st.markdown('<div class="oms-card">', unsafe_allow_html=True)

    # 外層：左品項、右輸入區
    left, right = st.columns([2.2, 3.8], gap="large")

    with left:
        st.markdown(f'<div class="oms-name">{it["name"]}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="oms-meta">單價：{it["price"]:.1f} ｜ 庫存基準：{BASE_UNIT}</div>',
            unsafe_allow_html=True,
        )

    with right:
        st.markdown('<div class="oms-right-tight">', unsafe_allow_html=True)

        # 第一排：庫存數字 / 叫貨數字（同一排）
        n1, n2 = st.columns([NUM_RATIO, NUM_RATIO_2], gap="small")
        with n1:
            st.text_input(
                "庫存",
                key=f"{it['id']}_stock_qty",
                label_visibility="collapsed",
                placeholder=f"庫存({BASE_UNIT})",
            )
        with n2:
            st.text_input(
                "叫貨",
                key=f"{it['id']}_order_qty",
                label_visibility="collapsed",
                placeholder="叫貨",
            )

        # 第二排：包/箱切換（放下面，避免手機爆寬）
        st.radio(
            "叫貨單位",
            ORDER_UNITS,
            key=f"{it['id']}_order_unit",
            horizontal=True,
            label_visibility="collapsed",
        )

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

with st.expander("Debug"):
    st.write(st.session_state)
