import streamlit as st

# =========================
# Page config
# =========================
st.set_page_config(page_title="OMS Compact Row Test (Unit Popover)", layout="wide")

# =========================
# CSS (密度 + 手機不爆版 + 膠囊按鈕)
# =========================
st.markdown(
    """
<style>
/* 內容寬度與 padding（避免手機左右被吃掉） */
.block-container{
  max-width: 1100px;
  padding-top: 1.2rem;
  padding-bottom: 2rem;
}
@media (max-width: 640px){
  .block-container{
    padding-left: 10px !important;
    padding-right: 10px !important;
  }
}

/* 每個品項卡片 */
.item-card{
  padding: 12px 12px 10px 12px;
  border-radius: 14px;
  border: 1px solid rgba(120,120,120,0.18);
  margin-bottom: 12px;
}
.item-name{
  font-size: 18px;
  font-weight: 800;
  line-height: 1.2;
  margin-bottom: 2px;
}
.item-meta{
  font-size: 13px;
  opacity: 0.70;
  margin-bottom: 8px;
}

/* 讓 columns 在手機不要爆版 */
div[data-testid="stHorizontalBlock"]{
  column-gap: 10px;
}
@media (max-width: 640px){
  div[data-testid="stHorizontalBlock"]{
    flex-wrap: nowrap !important;
    column-gap: 10px !important;
  }
  div[data-testid="column"]{
    min-width: 0 !important;
  }
}

/* 輸入框高度（文字輸入，避免 +/-） */
div[data-testid="stTextInput"] input{
  height: 40px !important;
  padding: 0 10px !important;
  font-size: 16px !important;
}

/* popover 觸發按鈕（膠囊） */
div[data-testid="stPopover"] button{
  height: 34px !important;
  padding: 0 10px !important;
  border-radius: 999px !important;
  font-size: 14px !important;
}

/* popover 裡面的 selectbox 壓扁一點 */
div[data-testid="stSelectbox"] > div{
  min-height: 38px !important;
}
div[data-testid="stSelectbox"] div[role="combobox"]{
  min-height: 38px !important;
}

/* 下排（單位膠囊）間距：你想「再開一點」就改這裡 */
.unit-row{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;              /* ← 想更開：改 12 / 14 */
  margin-top: 6px;
}
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Utils
# =========================
def sanitize_qty_str(s: str) -> str:
    """
    允許空字串（代表還沒填）。
    其他就盡量轉 float，失敗就回 '0'
    """
    if s is None:
        return ""
    s = str(s).strip()
    if s == "":
        return ""
    try:
        x = float(s)
        # 你之前希望只到小數第一位：這裡就固定一位
        return f"{x:.1f}".rstrip("0").rstrip(".") if abs(x) >= 1 else f"{x:.1f}"
    except Exception:
        return "0"

def on_qty_change(key: str):
    st.session_state[key] = sanitize_qty_str(st.session_state.get(key, ""))

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
# Header
# =========================
st.title("OMS Compact Row Test（單位點了才出現）")
st.caption("目標：手機每品項只佔 2 行；數量用輸入框；單位用膠囊按鈕點開下拉（popover）。")
st.divider()

# =========================
# Render
# =========================
for it in items:
    iid = it["id"]

    # init state（一定要在 widget 前）
    st.session_state.setdefault(f"{iid}_stock_qty", "0")
    st.session_state.setdefault(f"{iid}_order_qty", "0")
    st.session_state.setdefault(f"{iid}_stock_unit", "KG")
    st.session_state.setdefault(f"{iid}_order_unit", "箱")

    st.markdown('<div class="item-card">', unsafe_allow_html=True)

    st.markdown(f'<div class="item-name">{it["name"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="item-meta">單價：{it["price"]:.1f}</div>', unsafe_allow_html=True)

    # 上排：庫存量 / 進貨量（兩欄）
    cL, cR = st.columns([1, 1], gap="small")

    with cL:
        st.text_input(
            "庫存量",
            key=f"{iid}_stock_qty",
            label_visibility="collapsed",
            on_change=on_qty_change,
            args=(f"{iid}_stock_qty",),
            placeholder="庫存",
        )

    with cR:
        st.text_input(
            "進貨量",
            key=f"{iid}_order_qty",
            label_visibility="collapsed",
            on_change=on_qty_change,
            args=(f"{iid}_order_qty",),
            placeholder="進貨",
        )

    # 下排：單位膠囊（兩欄）
    st.markdown('<div class="unit-row">', unsafe_allow_html=True)

    # 左：庫存單位（膠囊 → 點開下拉）
    with st.popover(f"{st.session_state[f'{iid}_stock_unit']} ▾", use_container_width=True):
        st.selectbox(
            "庫存單位",
            UNITS,
            key=f"{iid}_stock_unit",
            label_visibility="collapsed",
        )

    # 右：進貨單位（膠囊 → 點開下拉）
    with st.popover(f"{st.session_state[f'{iid}_order_unit']} ▾", use_container_width=True):
        st.selectbox(
            "進貨單位",
            UNITS,
            key=f"{iid}_order_unit",
            label_visibility="collapsed",
        )

    st.markdown("</div>", unsafe_allow_html=True)  # end unit-row
    st.markdown("</div>", unsafe_allow_html=True)  # end item-card

# =========================
# Debug
# =========================
with st.expander("Debug"):
    st.write(st.session_state)
