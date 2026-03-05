import re
import streamlit as st

# =========================
# Page
# =========================
st.set_page_config(page_title="OMS Compact Row Test v5", layout="wide")

# =========================
# CSS (safe, all inside string)
# =========================
st.markdown(
    """
<style>
/* --- container --- */
.block-container{
  padding-top: 1.2rem;
  padding-bottom: 2rem;
}

/* --- Make "columns" NOT wrap on mobile (single row), and control gap --- */
@media (max-width: 640px){
  div[data-testid="stHorizontalBlock"]{
    flex-wrap: nowrap !important;
    column-gap: 10px !important;   /* ✅ 中間間隙 */
    row-gap: 0px !important;
    align-items: center !important;
  }
  /* Let children shrink properly to avoid overflow */
  div[data-testid="column"]{
    min-width: 0 !important;
  }
}

/* --- Inputs compact height / padding --- */
div[data-testid="stTextInput"] input{
  height: 44px !important;
  padding: 0 10px !important;
  font-size: 16px !important;
}
div[data-testid="stSelectbox"] > div{
  height: 44px !important;
}

/* Select box internal (baseweb) */
div[data-testid="stSelectbox"] div[data-baseweb="select"]{
  min-width: 0 !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
  height: 44px !important;
  padding: 0 8px !important;
  font-size: 16px !important;
}

/* Reduce extra vertical spacing between widgets */
div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stTextInput"]),
div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stSelectbox"]){
  margin-bottom: 8px !important;
}

/* Slightly reduce label spacing (we won't show widget labels anyway) */
label{
  margin-bottom: 0.25rem !important;
}

/* Make the row feel "Excel-like" */
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

# =========================
# Helpers
# =========================
def sanitize_number_text(s: str, default: str = "0") -> str:
    """
    Keep only digits and a single dot. Return default if empty.
    This avoids session_state write-back issues: we sanitize on read.
    """
    if s is None:
        return default
    s = s.strip()
    if s == "":
        return default
    # allow digits and dot
    s = re.sub(r"[^0-9.]", "", s)
    # keep only first dot
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


# =========================
# Header
# =========================
st.title("OMS Compact Row Test v5（只測 UI）")
st.caption("目標：手機也同一排：庫存(數字+單位) / 進貨(數字+單位)。單位要看得到、有間隙、不超出螢幕。")

st.divider()

# =========================
# Fake data
# =========================
UNITS = ["KG", "包", "箱", "罐", "瓶", "袋"]
items = [
    {"item_id": "I001", "name": "測試原料", "price": 10.0},
    {"item_id": "I002", "name": "魚", "price": 0.0},
    {"item_id": "I003", "name": "高麗菜", "price": 50.0},
]

# =========================
# Render rows
# =========================
for it in items:
    item_id = it["item_id"]

    # init defaults BEFORE widgets
    st.session_state.setdefault(f"{item_id}_stock_qty", "0")
    st.session_state.setdefault(f"{item_id}_stock_unit", "KG")
    st.session_state.setdefault(f"{item_id}_order_qty", "0")
    st.session_state.setdefault(f"{item_id}_order_unit", "箱")

    st.markdown('<div class="item-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="item-name">{it["name"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="item-meta">單價：{it["price"]:.1f}</div>', unsafe_allow_html=True)

    # ✅ 關鍵：欄位比例（避免超出螢幕）
    # 數字欄寬、單位欄窄；中間靠 gap 控制間隙
    c1, c2, c3, c4 = st.columns([1.6, 0.9, 1.6, 0.9], gap="small")

    with c1:
        st.text_input(
            "庫存",
            key=f"{item_id}_stock_qty",
            label_visibility="collapsed",
            placeholder="0",
        )
    with c2:
        st.selectbox(
            "庫存單位",
            UNITS,
            key=f"{item_id}_stock_unit",
            label_visibility="collapsed",
        )
    with c3:
        st.text_input(
            "進貨",
            key=f"{item_id}_order_qty",
            label_visibility="collapsed",
            placeholder="0",
        )
    with c4:
        st.selectbox(
            "進貨單位",
            UNITS,
            key=f"{item_id}_order_unit",
            label_visibility="collapsed",
        )

    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# Debug (read-only, sanitized)
# =========================
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
