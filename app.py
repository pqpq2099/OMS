import re
import streamlit as st

st.set_page_config(page_title="OMS Compact Row Test v6", layout="wide")
st.markdown("""
<style>
/* 手機：把 Streamlit 預設左右 padding 變小，避免超出螢幕 */
@media (max-width: 640px){
  .block-container{
    padding-left: 6px !important;
    padding-right: 6px !important;
  }
}

/* 你的 row grid（如果你有用 data-oms-row / oms-row 這類 class，保留）
   沒有也沒關係，先不要加複雜條件 */
</style>
""", unsafe_allow_html=True)
st.markdown(
    """
<style>
/* ========== Base container ========== */
.block-container{
  padding-top: 1.1rem;
  padding-bottom: 2rem;
}

/* ========== Mobile: force 1-row and prevent overflow ========== */
@media (max-width: 640px){
  /* The horizontal block (columns row) */
  div[data-testid="stHorizontalBlock"]{
    flex-wrap: nowrap !important;
    column-gap: 6px !important;          /* ✅ gap 縮小，避免超出 */
    row-gap: 0px !important;
    align-items: center !important;
    overflow-x: hidden !important;       /* ✅ 防止橫向溢出 */
  }

  /* Each column can shrink */
  div[data-testid="column"]{
    min-width: 0 !important;
    overflow: hidden !important;
  }
}

/* ========== Inputs: compact + never exceed column width ========== */
div[data-testid="stTextInput"]{
  width: 100% !important;
  max-width: 100% !important;
}
div[data-testid="stTextInput"] input{
  width: 100% !important;
  max-width: 100% !important;
  height: 44px !important;
  padding: 0 8px !important;            /* ✅ 內距縮小 */
  font-size: 16px !important;
  box-sizing: border-box !important;
}

/* Selectbox container */
div[data-testid="stSelectbox"]{
  width: 100% !important;
  max-width: 100% !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"]{
  width: 100% !important;
  max-width: 100% !important;
  min-width: 0 !important;
}

/* Select visual box */
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
  height: 44px !important;
  padding: 0 6px !important;            /* ✅ 內距縮小 */
  font-size: 16px !important;
  box-sizing: border-box !important;
}

/* Reduce extra vertical spacing between widgets */
div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stTextInput"]),
div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stSelectbox"]){
  margin-bottom: 8px !important;
}

/* Row card styling */
.item-card{
  padding: 14px 12px;
  border-radius: 14px;
  border: 1px solid rgba(120,120,120,0.18);
  margin-bottom: 14px;
}
.item-name{
  font-size: 22px;
  font-weight: 800;
  margin: 0 0 4px 0;
}
.item-meta{
  font-size: 14px;
  opacity: 0.7;
  margin: 0 0 10px 0;
}
</style>
""",
    unsafe_allow_html=True,
)

def sanitize_number_text(s: str, default: str = "0") -> str:
    if s is None:
        return default
    s = s.strip()
    if s == "":
        return default
    s = re.sub(r"[^0-9.]", "", s)
    if s.count(".") > 1:
        parts = s.split(".")
        s = parts[0] + "." + "".join(parts[1:])
    if s in ("", "."):
        return default
    return s

def get_float_from_text(key: str, default: float = 0.0) -> float:
    txt = sanitize_number_text(st.session_state.get(key, "0"))
    try:
        return float(txt)
    except Exception:
        return default


st.title("OMS Compact Row Test v6（只測 UI）")
st.caption("目標：手機也同一排，且不超出螢幕。庫存(數字+單位) / 進貨(數字+單位)。")
st.divider()

UNITS = ["KG", "包", "箱", "罐", "瓶", "袋"]
items = [
    {"item_id": "I001", "name": "測試原料", "price": 10.0},
    {"item_id": "I002", "name": "魚", "price": 0.0},
    {"item_id": "I003", "name": "高麗菜", "price": 50.0},
]

for it in items:
    item_id = it["item_id"]

    st.session_state.setdefault(f"{item_id}_stock_qty", "0")
    st.session_state.setdefault(f"{item_id}_stock_unit", "KG")
    st.session_state.setdefault(f"{item_id}_order_qty", "0")
    st.session_state.setdefault(f"{item_id}_order_unit", "箱")

    st.markdown('<div class="item-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="item-name">{it["name"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="item-meta">單價：{it["price"]:.1f}</div>', unsafe_allow_html=True)

    # ✅ 更窄欄位比例（避免手機超出）
    c1, c2, c3, c4 = st.columns([1.35, 0.75, 1.35, 0.75], gap="small")

    with c1:
        st.text_input("庫存", key=f"{item_id}_stock_qty", label_visibility="collapsed", placeholder="0")
    with c2:
        st.selectbox("庫存單位", UNITS, key=f"{item_id}_stock_unit", label_visibility="collapsed")
    with c3:
        st.text_input("進貨", key=f"{item_id}_order_qty", label_visibility="collapsed", placeholder="0")
    with c4:
        st.selectbox("進貨單位", UNITS, key=f"{item_id}_order_unit", label_visibility="collapsed")

    st.markdown("</div>", unsafe_allow_html=True)

with st.expander("Debug（讀取時才清洗，不回寫 session_state）"):
    rows = []
    for it in items:
        item_id = it["item_id"]
        rows.append(
            {
                "item": it["name"],
                "stock_qty(text)": st.session_state.get(f"{item_id}_stock_qty"),
                "stock_qty(num)": get_float_from_text(f"{item_id}_stock_qty"),
                "stock_unit": st.session_state.get(f"{item_id}_stock_unit"),
                "order_qty(text)": st.session_state.get(f"{item_id}_order_qty"),
                "order_qty(num)": get_float_from_text(f"{item_id}_order_qty"),
                "order_unit": st.session_state.get(f"{item_id}_order_unit"),
            }
        )
    st.write(rows)

