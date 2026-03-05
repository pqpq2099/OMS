import streamlit as st
from datetime import date

# ============================================================
# [0] Page config
# ============================================================
st.set_page_config(page_title="OMS UI Stable Size Demo", layout="wide")

# ============================================================
# [1] CSS（只做：間距微調 + 移除 number_input stepper；不縮元件寬度）
# ============================================================
st.markdown(
    """
<style>
/* 容器：稍微收斂桌機寬度，避免空得太誇張（但不會把元件變小） */
.block-container{
  max-width: 1100px !important;
  padding-left: 1rem !important;
  padding-right: 1rem !important;
  padding-top: 1rem !important;
  padding-bottom: 2rem !important;
}

/* columns 左右 padding 小一點（只是讓行內更緊湊） */
div[data-testid="column"]{
  padding-left: .25rem !important;
  padding-right: .25rem !important;
}

/* 卡片外框 */
.orivia-item{
  border: 1px solid rgba(49,51,63,.15);
  border-radius: 12px;
  padding: 12px 12px 10px 12px;
  margin-bottom: 10px;
}

/* 品名/資訊文字 */
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

/* ✅ 只移除 stepper，不動寬度（避免你說的格子變怪） */
div[data-testid="stNumberInput"] button { display: none !important; }
div[data-testid="stNumberInput"] div:has(> button){ display:none !important; }

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
st.write("桌機：同一行（庫+單位 / 進+單位）。手機：不滑動，必要時自動變兩行（庫一行、進一行）。")

top1, top2 = st.columns([2.2, 1.2], gap="small")
with top1:
    st.selectbox("分店", ["ORIVIA_001 (STORE_000001)", "ORIVIA_002 (STORE_000002)"], index=0)
with top2:
    st.date_input("日期", value=date(2026, 3, 5))

st.selectbox("廠商（可先選，方便分段點貨）", ["(全部廠商)", "VENDOR_A", "VENDOR_B"], index=0)
st.divider()

# ============================================================
# [4] Rows
#   核心策略：
#   - 不再強制 nowrap / 不做橫向滑動
#   - 讓 Streamlit 在手機自然換行
#   - 欄位比例：數字較寬、單位較窄（但都維持正常大小）
# ============================================================
for it in items:
    k = it["item_id"]

    st.markdown('<div class="orivia-item">', unsafe_allow_html=True)

    st.markdown(f'<div class="orivia-name">{it["item_name_zh"]}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="orivia-meta">單價：{it["unit_price"]:.2f} ｜ 上次叫貨：{it["last_order"]} ｜ 建議：{it["suggest"]:.1f}</div>',
        unsafe_allow_html=True,
    )

    # ✅ 桌機通常會維持同一行；手機會自然換行，不會需要滑動
    c1, c2, c3, c4 = st.columns([1.4, 0.9, 1.4, 0.9], gap="small")

    with c1:
        st.number_input(
            "庫",
            min_value=0.0,
            value=0.0,
            step=0.5,
            format="%.1f",
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
            step=0.5,
            format="%.1f",
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
