import streamlit as st
from datetime import date

# ============================================================
# [0] Page config
# ============================================================
st.set_page_config(page_title="OMS UI Compact Demo", layout="wide")

# ============================================================
# [1] Global CSS (核心：把 number_input / selectbox 變窄 + 移除 stepper + 壓縮間距)
# ============================================================
st.markdown(
    """
<style>
/* --------- 整體容器：左右 padding 壓小 --------- */
.block-container{
  padding-left: 1rem !important;
  padding-right: 1rem !important;
  padding-top: 1rem !important;
  padding-bottom: 2rem !important;
}

/* --------- columns：減少欄位間的左右 padding --------- */
div[data-testid="column"]{
  padding-left: .2rem !important;
  padding-right: .2rem !important;
}

/* --------- 讓每一列更緊湊 --------- */
div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stHorizontalBlock"]) {
  margin-bottom: .35rem !important;
}

/* --------- 卡片外框（可選） --------- */
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
   [A] number_input：縮到像 POS 那樣，並移除 +/- stepper
   ============================================================ */

/* number input 外框限制寬度 */
div[data-testid="stNumberInput"]{
  min-width: 64px !important;
  max-width: 78px !important;
}

/* number input 輸入框本體：padding/font 縮小 */
div[data-testid="stNumberInput"] input{
  padding: 2px 6px !important;
  font-size: 14px !important;
  line-height: 1.2 !important;
}

/* 移除 stepper：不同版本 Streamlit 會有不同 DOM，這裡用多重選擇器硬拆 */
div[data-testid="stNumberInput"] button{
  display: none !important;
}
div[data-testid="stNumberInput"] [role="spinbutton"] + div{
  display: none !important;
}
div[data-testid="stNumberInput"] div:has(> button){
  display: none !important;
}

/* ============================================================
   [B] selectbox：縮小 + 壓掉右側箭頭區/內距
   ============================================================ */
div[data-testid="stSelectbox"]{
  min-width: 56px !important;
  max-width: 78px !important;
}

/* selectbox 外層 */
div[data-testid="stSelectbox"] > div{
  padding: 0 !important;
}

/* selectbox 顯示區（含箭頭那塊） */
div[data-testid="stSelectbox"] div[role="combobox"]{
  padding: 2px 6px !important;
  font-size: 14px !important;
  min-height: 30px !important;
}

/* 右側箭頭容器縮小（不同版本 class 不同，用 role 旁支抓） */
div[data-testid="stSelectbox"] div[role="combobox"] svg{
  width: 16px !important;
  height: 16px !important;
}

/* label 取消高度佔位（不想要 label 撐高就用空字串 label） */
label{
  margin-bottom: 0 !important;
}

/* ============================================================
   [C] 手機版：強制同一行不要直排（避免 columns 自動堆疊）
   這是關鍵：把 HorizontalBlock 變成可水平滾動，而不是直排
   ============================================================ */
@media (max-width: 768px){
  div[data-testid="stHorizontalBlock"]{
    flex-wrap: nowrap !important;
    overflow-x: auto !important;
    gap: .35rem !important;
  }
  /* 讓每個 column 不要被壓到變形 */
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
    {"item_id": "ITEM_0001", "item_name_zh": "測試原料", "unit_price": 10.00, "last_order": "-", "suggest": 1.0, "stock_units": ["KG", "包"], "order_units": ["箱", "包"]},
    {"item_id": "ITEM_0002", "item_name_zh": "魚", "unit_price": 0.00, "last_order": "-", "suggest": 1.0, "stock_units": ["包"], "order_units": ["包"]},
    {"item_id": "ITEM_0003", "item_name_zh": "高麗菜", "unit_price": 50.00, "last_order": "-", "suggest": 1.0, "stock_units": ["包", "KG"], "order_units": ["包", "箱"]},
]

# ============================================================
# [3] Header (模擬你現在的叫貨頁)
# ============================================================
st.write("手機：品名一行；輸入一行（庫+單位 / 進+單位 同一行）。")

top1, top2 = st.columns([2.2, 1.2])
with top1:
    st.selectbox("分店", ["ORIVIA_001 (STORE_000001)", "ORIVIA_002 (STORE_000002)"], index=0)
with top2:
    st.date_input("日期", value=date(2026, 3, 5))

st.selectbox("廠商（可先選，方便分段點貨）", ["(全部廠商)", "VENDOR_A", "VENDOR_B"], index=0)

st.divider()

# ============================================================
# [4] Item rows
#   - 品名（只顯示中文）
#   - 下方只保留：單價 / 上次叫貨 / 建議
#   - 輸入行：庫存數字 + 庫存單位 + 進貨數字 + 進貨單位（同一行）
#   - columns 比例：數字(較寬) / 單位(較窄) / 數字(較寬) / 單位(較窄)
# ============================================================
for it in items:
    item_key = it["item_id"]

    # 外框卡片（用 HTML 包一層）
    st.markdown('<div class="orivia-item">', unsafe_allow_html=True)

    # 品名（只顯示中文優先）
    st.markdown(f'<div class="orivia-name">{it["item_name_zh"]}</div>', unsafe_allow_html=True)

    # meta info（只保留：單價／上次叫貨／建議）
    st.markdown(
        f'<div class="orivia-meta">單價：{it["unit_price"]:.2f} ｜ 上次叫貨：{it["last_order"]} ｜ 建議：{it["suggest"]:.1f}</div>',
        unsafe_allow_html=True,
    )

    # 輸入行：同一行（庫+單位 / 進+單位）
    c1, c2, c3, c4 = st.columns([1.25, 0.75, 1.25, 0.75])

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

    st.markdown("</div>", unsafe_allow_html=True)

# ============================================================
# [5] Debug view (你可以先看 state 長怎樣)
# ============================================================
with st.expander("Debug：目前輸入值"):
    out = {}
    for it in items:
        item_key = it["item_id"]
        out[item_key] = {
            "stock_qty": st.session_state.get(f"{item_key}_stock_qty"),
            "stock_unit": st.session_state.get(f"{item_key}_stock_unit"),
            "order_qty": st.session_state.get(f"{item_key}_order_qty"),
            "order_unit": st.session_state.get(f"{item_key}_order_unit"),
        }
    st.json(out)
