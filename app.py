import streamlit as st

st.set_page_config(page_title="OMS Compact Row Test", layout="wide")

st.markdown("""
<style>
/* 基本容器縮一點，手機邊界不要吃太多 */
@media (max-width: 640px){
  .block-container{ padding-left:10px !important; padding-right:10px !important; }
}

/* 卡片 */
.item-card{
  padding: 14px 12px;
  border-radius: 14px;
  border: 1px solid rgba(120,120,120,0.18);
  margin-bottom: 12px;
}

/* ---- 桌機版：左品項，右四欄（庫存/單位/進貨/單位）---- */
.row-grid{
  display: grid;
  grid-template-columns: 2.2fr 1fr 0.9fr 1fr 0.9fr;
  grid-template-rows: auto auto; /* header + inputs */
  column-gap: 10px;
  row-gap: 6px;
  align-items: center;
}

/* header 字 */
.hd{
  font-size: 12px;
  opacity: 0.7;
  font-weight: 600;
  padding-left: 2px;
}

/* 品項資訊 */
.item-name{
  font-size: 18px;
  font-weight: 800;
  line-height: 1.2;
}
.item-meta{
  font-size: 12px;
  opacity: 0.7;
  margin-top: 4px;
}

/* 讓 Streamlit 元件更緊湊 */
div[data-testid="stTextInput"] input{
  height: 38px !important;
  padding: 0 10px !important;
  font-size: 16px !important;
}
div[data-testid="stSelectbox"] > div{
  height: 38px !important;
}

/* ---- 手機版：改成三行（品項一行；數字一行；單位一行）---- */
@media (max-width: 640px){
  .row-grid{
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto auto auto;
    column-gap: 8px;
    row-gap: 6px;
  }

  /* 品項跨兩欄 */
  .cell-item{ grid-column: 1 / -1; }

  /* 手機不顯示 header（省高度） */
  .cell-hd{ display:none; }
}
</style>
""", unsafe_allow_html=True)

st.title("OMS Compact Row Test（對齊版）")
st.caption("桌機：左品項 / 右：庫存-單位-進貨-單位 對齊。手機：品項一行、數字一行、單位一行。")
st.divider()

UNITS = ["KG","包","箱","袋"]

items = [
  {"id":"I001","name":"測試原料","price":10.0},
  {"id":"I002","name":"魚","price":0.0},
  {"id":"I003","name":"高麗菜","price":50.0},
]

def ti(key):
  return st.text_input("", key=key, label_visibility="collapsed")

def sb(key, options):
  return st.selectbox("", options, key=key, label_visibility="collapsed")

for item in items:
  sid = item["id"]

  st.session_state.setdefault(f"{sid}_stock_qty", "0")
  st.session_state.setdefault(f"{sid}_stock_unit", "KG")
  st.session_state.setdefault(f"{sid}_order_qty", "0")
  st.session_state.setdefault(f"{sid}_order_unit", "箱")

  st.markdown('<div class="item-card">', unsafe_allow_html=True)
  st.markdown('<div class="row-grid">', unsafe_allow_html=True)

  # ---- Row 1: header（桌機才顯示）----
  st.markdown(f"""
    <div class="cell-item cell-hd"></div>
    <div class="cell-hd hd">庫存</div>
    <div class="cell-hd hd">單位</div>
    <div class="cell-hd hd">進貨</div>
    <div class="cell-hd hd">單位</div>
  """, unsafe_allow_html=True)

  # ---- Row 2+: item + inputs ----
  # 用 columns 只是為了把 Streamlit 元件塞進 grid 的位置：用 st.container + markdown 佔位不夠，必須用 st.columns hack 配合占位
  # 這裡採用：先在 grid 放 5 個「定位容器」，每格各放一個 Streamlit 元件

  c_item, c_sqty, c_sunit, c_oqty, c_ounit = st.columns([2.2,1,0.9,1,0.9], gap="small")

  with c_item:
    st.markdown(f'<div class="cell-item item-name">{item["name"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="item-meta">單價：{item["price"]:.1f}</div>', unsafe_allow_html=True)

  with c_sqty:
    ti(f"{sid}_stock_qty")
  with c_sunit:
    sb(f"{sid}_stock_unit", UNITS)

  with c_oqty:
    ti(f"{sid}_order_qty")
  with c_ounit:
    sb(f"{sid}_order_unit", UNITS)

  st.markdown("</div>", unsafe_allow_html=True)   # row-grid
  st.markdown("</div>", unsafe_allow_html=True)   # item-card

with st.expander("Debug"):
  st.write(st.session_state)
