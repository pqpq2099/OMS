import streamlit as st

st.set_page_config(page_title="OMS Compact Row Test", layout="wide")

# =========================
# CSS: 只做「控寬 + 同一行 + 隱藏 stepper」
# =========================
st.markdown(
    """
<style>
/* --- 基本：縮掉 container padding，避免手機浪費空間 --- */
.block-container { padding-top: 1rem; padding-bottom: 2rem; }

/* --- 隱藏 number_input 的 +/- stepper（不同版本可能有差異，兩種都加） --- */
button[aria-label="Increment"], button[aria-label="Decrement"] { display: none !important; }
[data-testid="stNumberInputStepUp"], [data-testid="stNumberInputStepDown"] { display: none !important; }

/* --- 讓「同一行」成立的核心：把下一個 widget 的外層 div 改成 inline-block --- */
/* 我們用「marker + 下一個元素」這種方式，精準控制 4 個 widget 都變 inline-block */
.omslab { margin: 0.35rem 0 0.25rem 0; font-weight: 700; }
.omsm { display: block; height: 0px; } /* marker 本身不佔空間 */

.omsm + div { 
  display: inline-block !important;
  vertical-align: top !important;
  margin-right: 8px !important;   /* 欄位間距 */
}

/* --- 控制寬度：桌機 & 手機都用固定寬（避免 Streamlit 自動拉滿） --- */
/* 數字框（庫存/進貨） */
.omsw-num + div { width: 96px !important; min-width: 96px !important; max-width: 96px !important; }
/* 單位下拉（庫存/進貨） */
.omsw-unit + div { width: 76px !important; min-width: 76px !important; max-width: 76px !important; }

/* 讓 input / select 本體吃滿我們定的寬度 */
.omsm + div [data-testid="stNumberInput"] { width: 100% !important; }
.omsm + div [data-testid="stSelectbox"] { width: 100% !important; }

/* 下拉箭頭區、padding 稍微縮小（避免單位被擠到只剩符號） */
.omsm + div [data-baseweb="select"] > div {
  padding-left: 8px !important;
  padding-right: 28px !important; /* 保留箭頭空間 */
}

/* number_input 的 input padding 縮小一點 */
.omsm + div input {
  padding-left: 8px !important;
  padding-right: 8px !important;
}

/* --- 手機：再更緊一點（避免超出螢幕） --- */
@media (max-width: 640px) {
  .block-container { padding-left: 0.8rem; padding-right: 0.8rem; }

  .omsm + div { margin-right: 6px !important; }

  .omsw-num + div { width: 88px !important; min-width: 88px !important; max-width: 88px !important; }
  .omsw-unit + div { width: 68px !important; min-width: 68px !important; max-width: 68px !important; }
}
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# 測試資料
# =========================
ITEMS = [
    {"name": "測試原料", "price": 10.0, "stock_unit": ["KG", "包", "箱"], "order_unit": ["箱", "包", "KG"]},
    {"name": "魚", "price": 0.0, "stock_unit": ["包", "KG", "箱"], "order_unit": ["包", "箱", "KG"]},
    {"name": "高麗菜", "price": 50.0, "stock_unit": ["包", "KG"], "order_unit": ["包", "箱"]},
]

st.title("OMS Compact Row Test（只測 UI）")

st.caption("目標：手機也要維持同一行：庫存(數字+單位) / 進貨(數字+單位)，不出現 +/-，不超出螢幕。")

st.divider()

# =========================
# Row renderer (四個 widget 以 marker + CSS 控寬，強制同一行)
# =========================
def render_item_row(idx: int, it: dict):
    st.markdown(f'<div class="omslab">{it["name"]}</div>', unsafe_allow_html=True)
    st.caption(f'單價：{it["price"]:.1f}')

    # 庫存數字
    st.markdown('<span class="omsm omsw-num"></span>', unsafe_allow_html=True)
    stock_qty = st.number_input(
        "庫存數字",
        min_value=0.0,
        value=0.0,
        step=0.0,  # 避免顯示 step 的最佳做法仍是 CSS 隱藏，但這裡也設 0
        format="%.1f",
        key=f"stock_qty_{idx}",
        label_visibility="collapsed",
    )

    # 庫存單位
    st.markdown('<span class="omsm omsw-unit"></span>', unsafe_allow_html=True)
    stock_unit = st.selectbox(
        "庫存單位",
        it["stock_unit"],
        index=0,
        key=f"stock_unit_{idx}",
        label_visibility="collapsed",
    )

    # 進貨數字
    st.markdown('<span class="omsm omsw-num"></span>', unsafe_allow_html=True)
    order_qty = st.number_input(
        "進貨數字",
        min_value=0.0,
        value=0.0,
        step=0.0,
        format="%.1f",
        key=f"order_qty_{idx}",
        label_visibility="collapsed",
    )

    # 進貨單位
    st.markdown('<span class="omsm omsw-unit"></span>', unsafe_allow_html=True)
    order_unit = st.selectbox(
        "進貨單位",
        it["order_unit"],
        index=0,
        key=f"order_unit_{idx}",
        label_visibility="collapsed",
    )

    # 換行（結束 inline-block）
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

    return stock_qty, stock_unit, order_qty, order_unit


for i, it in enumerate(ITEMS):
    render_item_row(i, it)
    st.markdown("<hr/>", unsafe_allow_html=True)

with st.expander("Debug：目前輸入值"):
    st.json({k: v for k, v in st.session_state.items() if any(x in k for x in ["stock_", "order_"])})
