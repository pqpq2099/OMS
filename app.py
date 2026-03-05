import streamlit as st
from datetime import date

# ============================================================
# [0] Page config
# ============================================================
st.set_page_config(page_title="OMS Mobile 1-Row Template", layout="wide")

# ============================================================
# [1] CSS：核心就是「固定寬度 + columns 不撐滿 + 不滑動」
# ============================================================
st.markdown(
    """
<style>
/* --------- 容器不要太寬，避免桌機空得離譜 --------- */
.block-container{
  max-width: 980px !important;
  padding-left: 1rem !important;
  padding-right: 1rem !important;
  padding-top: 1rem !important;
  padding-bottom: 2rem !important;
}

/* --------- 卡片外框 --------- */
.orivia-item{
  border: 1px solid rgba(49,51,63,.15);
  border-radius: 12px;
  padding: 12px 12px 10px 12px;
  margin-bottom: 10px;
}
.orivia-name{
  font-weight: 700;
  font-size: 16px;
  margin: 0 0 6px 0;
}
.orivia-meta{
  font-size: 13px;
  color: rgba(49,51,63,.65);
  margin: 0 0 10px 0;
}

/* ============================================================
   [A] 讓 columns 不要撐滿整行（關鍵）
   - 這樣固定寬度的元件才會靠左貼在一起，不會散開
   ============================================================ */
div[data-testid="stHorizontalBlock"]{
  gap: .45rem !important;
  flex-wrap: nowrap !important;     /* ✅ 同一行 */
  overflow-x: hidden !important;    /* ✅ 不滑動 */
}
div[data-testid="column"]{
  flex: 0 0 auto !important;        /* ✅ 不撐滿 */
  width: auto !important;
  padding-left: .15rem !important;
  padding-right: .15rem !important;
}

/* ============================================================
   [B] number_input：固定寬度（能輸入 3 位數就夠）
   ============================================================ */
div[data-testid="stNumberInput"]{
  width: 92px !important;           /* ✅ 三位數夠用 */
  min-width: 92px !important;
  max-width: 92px !important;
}
div[data-testid="stNumberInput"] input{
  padding: 4px 8px !important;
  font-size: 14px !important;
}

/* ✅ 移除 +/- stepper（多版本兼容） */
div[data-testid="stNumberInput"] button { display:none !important; }
div[data-testid="stNumberInput"] div:has(> button){ display:none !important; }

/* ============================================================
   [C] selectbox：固定窄寬（單位下拉）
   ============================================================ */
div[data-testid="stSelectbox"]{
  width: 74px !important;
  min-width: 74px !important;
  max-width: 74px !important;
}
div[data-testid="stSelectbox"] div[role="combobox"]{
  padding: 4px 8px !important;
  font-size: 14px !important;
  min-height: 34px !important;
}

/* label 不要佔位（我們用 collapsed） */
label{ margin-bottom: 0 !important; }

/* 手機：維持同一行、不滑動（如果真的塞不下，就代表要再縮寬度或改單位顯示） */
@media (max-width: 768px){
  .block-container{ max-width: 100% !important; }
}
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# [2] Demo data
# ============================================================
items = [
    {"item_id": "ITEM_0001", "item_name_zh": "測試原料", "unit_price": 10.00, "last_order": "-", "suggest": 1.0,
     "stock_units": ["KG", "包"], "order_units": ["箱", "包"]},
    {"item_id": "ITEM_0002", "item_name_zh": "魚", "unit_price": 0.00, "last_order": "-", "suggest": 1.0,
     "stock_units": ["包"], "order_units": ["包"]},
    {"item_id": "ITEM_0003", "item_name_zh": "高麗菜", "unit_price": 50.00, "last_order": "-", "suggest": 1.0,
     "stock_units": ["包", "KG"], "order_units": ["包", "箱"]},
]

# ============================================================
# [3] Header
# ============================================================
st.write("測試模板：手機同一行、不滑動；數字框三位數寬度；單位下拉很窄。")

top1, top2 = st.columns([2.2, 1.2])
with top1:
    st.selectbox("分店", ["ORIVIA_001 (STORE_000001)", "ORIVIA_002 (STORE_000002)"], index=0)
with top2:
    st.date_input("日期", value=date(2026, 3, 5))

st.selectbox("廠商（可先選，方便分段點貨）", ["(全部廠商)", "VENDOR_A", "VENDOR_B"], index=0)
st.divider()

# ============================================================
# [4] Rows（重點：columns 比例不重要了，因為寬度由 CSS 固定）
# ============================================================
for it in items:
    k = it["item_id"]
    st.markdown('<div class="orivia-item">', unsafe_allow_html=True)

    st.markdown(f'<div class="orivia-name">{it["item_name_zh"]}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="orivia-meta">單價：{it["unit_price"]:.2f} ｜ 上次叫貨：{it["last_order"]} ｜ 建議：{it["suggest"]:.1f}</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)  # ✅ 這裡比例不用管，CSS 已經把它變成「不撐滿+固定寬」

    with c1:
        st.number_input(
            "庫",
            min_value=0.0,
            value=0.0,
            step=1.0,
            format="%.0f",
            key=f"{k}_stock_qty",
            label_visibility="collapsed",
        )
    with c2:
        st.selectbox(
            "庫單位",
            it["stock_units"],
            index=0,
            key=f"{k}_stock_unit",
            label_visibility="collapsed",
        )
    with c3:
        st.number_input(
            "進",
            min_value=0.0,
            value=0.0,
            step=1.0,
            format="%.0f",
            key=f"{k}_order_qty",
            label_visibility="collapsed",
        )
    with c4:
        st.selectbox(
            "進單位",
            it["order_units"],
            index=0,
            key=f"{k}_order_unit",
            label_visibility="collapsed",
        )

    st.markdown("</div>", unsafe_allow_html=True)

# ============================================================
# [5] Debug
# ============================================================
with st.expander("Debug：目前輸入值"):
    out = {}
    for it in items:
        k = it["item_id"]
        out[k] = {
            "stock_qty": st.session_state.get(f"{k}_stock_qty"),
            "stock_unit": st.session_state.get(f"{k}_stock_unit"),
            "order_qty": st.session_state.get(f"{k}_order_qty"),
            "order_unit": st.session_state.get(f"{k}_order_unit"),
        }
    st.json(out)
