import streamlit as st

# ============================================================
# OMS Compact Row Test - Full single-file demo (UI only)
# 目標：
# - 桌機：左=品項資訊；右=庫存數字/叫貨數字/包箱切換 (同一列)
# - 手機：維持同一列，不自動變直排、不超出螢幕
# - 庫存單位固定基準(顯示用)；叫貨單位用包/箱切換(可改)
# ============================================================

st.set_page_config(page_title="OMS Compact Row Test (Full)", layout="wide")

# -------------------------
# Tunables (你要改寬度就改這裡)
# -------------------------
MOBILE_BREAKPOINT = 640  # px

# 數字欄位寬度（手機/桌機）
MOBILE_NUM_W = 64        # px
DESKTOP_NUM_W = 92       # px

# 包箱切換區寬度（手機/桌機）
MOBILE_TOGGLE_W = 140    # px
DESKTOP_TOGGLE_W = 190   # px

# 欄位間距（手機/桌機）
MOBILE_GAP = 6           # px
DESKTOP_GAP = 10         # px

# 輸入框高度（手機/桌機）
INPUT_H = 38             # px

# -------------------------
# CSS
# -------------------------
st.markdown(
    f"""
<style>
/* 讓整體左右 padding 小一點（手機更省） */
@media (max-width: {MOBILE_BREAKPOINT}px){{
  .block-container{{
    padding-left: 8px !important;
    padding-right: 8px !important;
  }}
}}

/* 卡片 */
.item-card{{
  padding: 10px 10px;
  border-radius: 12px;
  border: 1px solid rgba(120,120,120,0.18);
  margin-bottom: 10px;
}}
.item-name{{
  font-size: 18px;
  font-weight: 800;
  line-height: 1.15;
}}
.item-meta{{
  font-size: 12px;
  opacity: 0.75;
  margin-top: 4px;
  margin-bottom: 8px;
}}
.hint-head{{
  font-size: 12px;
  opacity: .65;
  margin-bottom: 4px;
}}
/* 把每列底下 Streamlit 的空白 margin 壓小 */
div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stTextInput"]),
div[data-testid="stVerticalBlock"] > div:has(> div[role="radiogroup"]){{
  margin-bottom: 0px !important;
}}

/* 輸入框高度與字 */
div[data-testid="stTextInput"] input{{
  height: {INPUT_H}px !important;
  padding: 0 10px !important;
  font-size: 16px !important;
}}

/* ----- 核心：手機不要讓 columns 自動變直排 ----- */
@media (max-width: {MOBILE_BREAKPOINT}px){{
  div[data-testid="stHorizontalBlock"]{{
    flex-wrap: nowrap !important;
    gap: {MOBILE_GAP}px !important;
    align-items: center !important;
  }}
  div[data-testid="column"]{{
    min-width: 0 !important;        /* 允許縮到內容寬 */
  }}
}}

/* 桌機 columns gap */
@media (min-width: {MOBILE_BREAKPOINT+1}px){{
  div[data-testid="stHorizontalBlock"]{{
    gap: {DESKTOP_GAP}px !important;
    align-items: center !important;
  }}
}}

/* --- 控制「數字欄位」寬度：用 wrapper class 精準鎖 --- */
.numwrap-desktop div[data-testid="stTextInput"]{{ max-width: {DESKTOP_NUM_W}px !important; }}
.numwrap-mobile  div[data-testid="stTextInput"]{{ max-width: {MOBILE_NUM_W}px !important; }}

/* --- 控制「包箱切換」寬度 --- */
.togglewrap-desktop div[role="radiogroup"]{{ max-width: {DESKTOP_TOGGLE_W}px !important; }}
.togglewrap-mobile  div[role="radiogroup"]{{ max-width: {MOBILE_TOGGLE_W}px !important; }}

/* --- radio 做成小顆 pill，並縮高度 --- */
div[role="radiogroup"]{{
  gap: 6px !important;
}}
div[role="radiogroup"] label{{
  margin: 0 !important;
}}
div[role="radiogroup"] label > div{{
  padding: 6px 10px !important;
  border-radius: 10px !important;
}}
div[role="radiogroup"] label span{{
  font-size: 14px !important;
}}

/* 讓右側控制區不要撐爆 */
.ctrl-row{{
  display:flex;
  justify-content:flex-end;
  gap: {DESKTOP_GAP}px;
}}
@media (max-width: {MOBILE_BREAKPOINT}px){{
  .ctrl-row{{ gap: {MOBILE_GAP}px; }}
}}
</style>
""",
    unsafe_allow_html=True,
)

# -------------------------
# Header
# -------------------------
st.title("OMS Compact Row Test（庫存固定基準 / 叫貨包箱切換）")
st.caption("目標：桌機左品項右輸入；手機也維持同一排，不自動變直排、不超出螢幕。")
st.divider()

# -------------------------
# Fake data
# -------------------------
BASE_UNIT = "KG"                 # 庫存基準單位固定（顯示用）
ORDER_UNITS = ["包", "箱"]        # 叫貨單位：包/箱（之後可改成包/條/罐…）

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
    st.session_state.setdefault(f"{item_id}_order_unit", ORDER_UNITS[0])  # default 包

# -------------------------
# Render
# -------------------------
# 桌機才顯示欄位提示（避免你說「誰是誰」）
# 手機不顯示，省高度
is_mobile_hint = st.checkbox("（測試用）強制顯示欄位標題", value=False, help="桌機通常要顯示「庫存/叫貨/單位」，手機可關掉省空間")

for it in items:
    ensure_defaults(it["id"])

    st.markdown('<div class="item-card">', unsafe_allow_html=True)

    # 兩大區：左(品項) / 右(控制)
    left, right = st.columns([1.6, 1.4], gap="small")

    with left:
        st.markdown(f'<div class="item-name">{it["name"]}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="item-meta">單價：{it["price"]:.1f} / {BASE_UNIT}</div>',
            unsafe_allow_html=True,
        )

    with right:
        # 桌機提示：庫存 / 叫貨 / 包箱
        if is_mobile_hint:
            h1, h2, h3 = st.columns([0.9, 0.9, 1.2], gap="small")
            with h1: st.markdown('<div class="hint-head">庫存</div>', unsafe_allow_html=True)
            with h2: st.markdown('<div class="hint-head">叫貨</div>', unsafe_allow_html=True)
            with h3: st.markdown('<div class="hint-head">單位</div>', unsafe_allow_html=True)

        c1, c2, c3 = st.columns([0.9, 0.9, 1.2], gap="small")

        with c1:
            # 依螢幕套不同寬度 class（手機更小）
            st.markdown('<div class="numwrap-mobile numwrap-desktop">', unsafe_allow_html=True)
            st.text_input(
                "庫存",
                key=f"{it['id']}_stock_qty",
                label_visibility="collapsed",
                placeholder="庫",
            )
            st.markdown('</div>', unsafe_allow_html=True)

        with c2:
            st.markdown('<div class="numwrap-mobile numwrap-desktop">', unsafe_allow_html=True)
            st.text_input(
                "叫貨",
                key=f"{it['id']}_order_qty",
                label_visibility="collapsed",
                placeholder="進",
            )
            st.markdown('</div>', unsafe_allow_html=True)

        with c3:
            st.markdown('<div class="togglewrap-mobile togglewrap-desktop">', unsafe_allow_html=True)
            st.radio(
                "叫貨單位",
                ORDER_UNITS,
                key=f"{it['id']}_order_unit",
                horizontal=True,
                label_visibility="collapsed",
            )
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# Debug
# -------------------------
with st.expander("Debug (session_state)"):
    st.write(st.session_state)
