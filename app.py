import streamlit as st
from datetime import date

st.set_page_config(page_title="OMS UI - Compact Row Test", layout="wide")

# ============================================================
# CSS（只控制「同一排同時有 NumberInput + Selectbox」的那種列）
# 你只需要改兩個數字：
#   --numw: 數字欄寬度
#   --unitw: 單位欄寬度
# ============================================================
st.markdown("""
<style>
:root{
  --numw: 56px;     /* ✅ 數字欄：三位數很緊但可用（要更寬就 60/64） */
  --unitw: 44px;    /* ✅ 單位欄：KG/包/箱（要更寬就 48/52） */
  --gapw: 2px;      /* ✅ 欄位間距 */
  --font: 13px;     /* ✅ 字體 */
  --padx: 4px;      /* ✅ 左右內距 */
  --pady: 2px;      /* ✅ 上下內距 */
}

/* 不影響其他區塊（上面的分店/日期/廠商不會被壓扁） */
.block-container{ max-width: 980px; padding: 16px 16px 32px; }

/* 只鎖定：同一排同時含 NumberInput + Selectbox 的 row（也就是你那一排四格） */
div[data-testid="stHorizontalBlock"]
  :has(div[data-testid="stNumberInput"])
  :has(div[data-testid="stSelectbox"]){}

/* ✅ 真正作用的 selector：row 本體 */
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stNumberInput"]):has(div[data-testid="stSelectbox"]){
  display:flex !important;
  flex-direction: row !important;
  flex-wrap: nowrap !important;          /* 手機也不換行 */
  justify-content: flex-start !important;
  align-items: center !important;
  gap: var(--gapw) !important;
  width: fit-content !important;         /* 不要被撐滿 */
  max-width: 100% !important;
}

/* ✅ 把 Streamlit column 的「滿寬」屬性打掉 */
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stNumberInput"]):has(div[data-testid="stSelectbox"])
  > div[data-testid="column"]{
  flex: 0 0 auto !important;
  width: auto !important;
  max-width: none !important;
  min-width: 0 !important;
  padding: 0 !important;
  margin: 0 !important;
}

/* ✅ 用內容判斷，不靠第幾欄：NumberInput 的 column 固定 numw */
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stNumberInput"]):has(div[data-testid="stSelectbox"])
  > div[data-testid="column"]:has(div[data-testid="stNumberInput"]){
  flex: 0 0 var(--numw) !important;
  width: var(--numw) !important;
  max-width: var(--numw) !important;
  min-width: var(--numw) !important;
}

/* ✅ Selectbox 的 column 固定 unitw */
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stNumberInput"]):has(div[data-testid="stSelectbox"])
  > div[data-testid="column"]:has(div[data-testid="stSelectbox"]){
  flex: 0 0 var(--unitw) !important;
  width: var(--unitw) !important;
  max-width: var(--unitw) !important;
  min-width: var(--unitw) !important;
}

/* widget 本體：打掉 min-width，才能真的縮 */
div[data-testid="stNumberInput"],
div[data-testid="stSelectbox"]{
  width: 100% !important;
  min-width: 0 !important;
}

/* number input 外觀 */
div[data-testid="stNumberInput"] input{
  padding: var(--pady) var(--padx) !important;
  font-size: var(--font) !important;
  line-height: 1.1 !important;
}

/* selectbox：baseweb 本體也要打 min-width，否則會撐開 */
div[data-testid="stSelectbox"] div[data-baseweb="select"]{
  width: 100% !important;
  min-width: 0 !important;
}
div[data-testid="stSelectbox"] div[role="combobox"]{
  padding: var(--pady) 2px !important;  /* 單位欄要更省空間 */
  min-height: 26px !important;
  font-size: var(--font) !important;
}
div[data-testid="stSelectbox"] span{
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: clip !important;
}
div[data-testid="stSelectbox"] svg{
  width: 12px !important;
  height: 12px !important;
}

/* ✅ Stepper 永久移除（多版本一起抓） */
div[data-testid="stNumberInput"] button{ display:none !important; }
div[data-testid="stNumberInput"] svg{ display:none !important; }
div[data-testid="stNumberInput"] [data-baseweb="input"] button{ display:none !important; }

</style>
""", unsafe_allow_html=True)

# ============================================================
# Demo UI（你只看版面，不管資料）
# ============================================================
items = [
    {"id": "1", "name": "測試原料", "price": 10.0, "stock_units": ["KG", "包"], "order_units": ["箱", "包"]},
    {"id": "2", "name": "魚", "price": 0.0, "stock_units": ["包"], "order_units": ["包"]},
    {"id": "3", "name": "高麗菜", "price": 50.0, "stock_units": ["包", "KG"], "order_units": ["包", "箱"]},
]

a, b = st.columns([2, 1])
with a:
    st.selectbox("分店", ["ORIVIA_001 (STORE_000001)"], index=0)
with b:
    st.date_input("日期", value=date(2026, 3, 5))
st.selectbox("廠商（可先選，方便分段點貨）", ["(全部廠商)", "VENDOR_A"], index=0)

st.divider()

for it in items:
    st.markdown(f"**{it['name']}**")
    st.caption(f"單價：{it['price']:.2f}")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.number_input("", min_value=0, value=0, step=1, key=f"s_{it['id']}", label_visibility="collapsed")
    with c2:
        st.selectbox("", it["stock_units"], index=0, key=f"su_{it['id']}", label_visibility="collapsed")
    with c3:
        st.number_input("", min_value=0, value=0, step=1, key=f"o_{it['id']}", label_visibility="collapsed")
    with c4:
        st.selectbox("", it["order_units"], index=0, key=f"ou_{it['id']}", label_visibility="collapsed")

    st.markdown("---")
