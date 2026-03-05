import streamlit as st
from datetime import date

# ============================================================
# [0] Page config
# ============================================================
st.set_page_config(page_title="OMS UI Compact Demo", layout="wide")

# ============================================================
# [1] Global CSS
#   核心改動：
#   1) block-container 加 max-width：避免桌機超寬導致空隙巨大
#   2) columns 用「最後一格吃掉剩餘寬度」：讓 4 個控制項靠左貼齊
#   3) number_input / selectbox 變窄 + 移除 stepper
# ============================================================
st.markdown(
    """
<style>
/* --------- 整體容器：限制最大寬度，避免桌機空隙超大 --------- */
.block-container{
  max-width: 980px !important;      /* ✅ 這行是桌機“不要散開”的關鍵 */
  padding-left: 1rem !important;
  padding-right: 1rem !important;
  padding-top: 1rem !important;
  padding-bottom: 2rem !important;
}

/* --------- columns：減少欄位間的左右 padding --------- */
div[data-testid="column"]{
  padding-left: .15rem !important;
  padding-right: .15rem !important;
}

/* --------- 卡片外框 --------- */
.orivia-item{
  border: 1px solid rgba(49,51,63,.15);
  border-radius: 12px;
  padding: 12px 12px 10px 12px;
  margin-bottom: 10px;
}

/* --------- 品名/資訊文字 --------- */
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
   [A] number_input：縮窄 + 移除 +/- stepper
   ============================================================ */
div[data-testid="stNumberInput"]{
  min-width: 64px !important;
  max-width: 78px !important;
}
div[data-testid="stNumberInput"] input{
  padding: 2px 6px !important;
  font-size: 14px !important;
  line-height: 1.2 !important;
}

/* ✅ 更乾淨的移除 stepper（多版本兼容） */
div[data-testid="stNumberInput"] button { display: none !important; }
div[data-testid="stNumberInput"] div:has(> button){ display:none !important; }

/* ============================================================
   [B] selectbox：縮窄 + 壓縮箭頭區
   ============================================================ */
div[data-testid="stSelectbox"]{
  min-width: 56px !important;
  max-width: 78px !important;
}
div[data-testid="stSelectbox"] div[role="combobox"]{
  padding: 2px 6px !important;
  font-size: 14px !important;
  min-height: 30px !important;
}
div[data-testid="stSelectbox"] div[role="combobox"] svg{
  width: 16px !important;
  height: 16px !important;
}

/* label 不要佔高度（我們用 collapsed） */
label{ margin-bottom: 0 !important; }

/* ============================================================
   [C] 手機：同一行、不直排，必要時可橫向滑動
   ============================================================ */
@media (max-width: 768px){
  .block-container{ max-width: 100% !important; }

  div[data-testid="stHorizontalBlock"]{
    flex-wrap: nowrap !important;
    overflow-x: auto !important;
    gap: .35rem !important;
  }
  div[data-testid="column"]{
    flex: 0 0 auto !important;
  }
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
# [3] Header (模擬叫貨頁)
# ============================================================
st.write("手機：品名一行；輸入一行（庫+單位 / 進+單位 同一行）。")

top1, top2 = st.columns([2.2, 1.2], gap="small")
with top1:
    st.selectbox("分店", ["ORIVIA_001 (STORE_000001)", "ORIVIA_002 (STORE_000002)"], index=0)
with top2:
    st.date_input("日期", value=date(2026, 3, 5))

st.selectbox("廠商（可先選，方便分段點貨）", ["(全部廠商)", "VENDOR_A", "VENDOR_B"], index=0)

st.divider()

# ============================================================
# [4] Item rows
#   ✅ 關鍵：用 5 columns，最後一格當「吸寬欄」吃掉剩餘空間
#   這樣前 4 個控制項會靠左緊貼，不會散開
# ============================================================
for it in items:
    item_key = it["item_id"]

    st.markdown('<div class="orivia-item">', unsafe_allow_html=True)

    st.markdown(f'<div class="orivia-name">{it["item_name_zh"]}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="orivia-meta">單價：{it["unit_price"]:.2f} ｜ 上次叫貨：{it["last_order"]} ｜ 建議：{it["suggest"]:.1f}</div>',
        unsafe_allow_html=True,
    )

    # ✅ 前四格放控制項，第五格吸掉剩餘空間
    c1, c2, c3, c4, c5 = st.columns([0.9, 0.75, 0.9, 0.75, 6.0], gap="small")

    with c1:
        st.number_input(
            "庫",
            min_value=0.0,
            value=0.0,
            step=0.1,
            format="%.1f",
            key=f"{item_key}_stock_qty",
            label_visibility="collapsed",
        )

    with c2:
        st.selectbox(
            "庫單位",
            it["stock_units"],
            index=0,
            key=f"{item_key}_stock_unit",
            label_visibility="collapsed",
        )

    with c3:
        st.number_input(
            "進",
            min_value=0.0,
            value=0.0,
            step=0.1,
            format="%.1f",
            key=f"{item_key}_order_qty",
            label_visibility="collapsed",
        )

    with c4:
        st.selectbox(
            "進單位",
            it["order_units"],
            index=0,
            key=f"{item_key}_order_unit",
            label_visibility="collapsed",
        )

    with c5:
        # 吸寬欄：什麼都不放
        st.write("")

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
