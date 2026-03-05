<style>
/* =========================
   基本容器
========================= */
.block-container{
  max-width: 980px !important;
  padding: 1rem !important;
}

/* 卡片 */
.orivia-item{
  border: 1px solid rgba(49,51,63,.15);
  border-radius: 12px;
  padding: 12px 12px 10px 12px;
  margin-bottom: 10px;
}
.orivia-name{ font-weight:700; font-size:16px; margin:0 0 6px 0; }
.orivia-meta{ font-size:13px; color:rgba(49,51,63,.65); margin:0 0 10px 0; }

/* =========================
   ✅ 關鍵：強制 columns 永遠橫向（含手機）
   不管 Streamlit breakpoint 怎麼改，都用 row
========================= */
.orivia-row div[data-testid="stHorizontalBlock"]{
  display:flex !important;
  flex-direction: row !important;
  flex-wrap: nowrap !important;
  gap: 8px !important;
  align-items: center !important;
}

/* 有些版本手機會改成 stVerticalBlock：也強制橫向 */
.orivia-row div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"]{
  display:flex !important;
  flex-direction: row !important;
  flex-wrap: nowrap !important;
  gap: 8px !important;
}

/* =========================
   ✅ 不用 nth-child，改用 :has() 判斷內容來固定寬度
   number_input → 92px
   selectbox    → 78px
========================= */
.orivia-row div[data-testid="column"]{
  padding: 0 !important;
  margin: 0 !important;
  min-width: 0 !important;
}

.orivia-row div[data-testid="column"]:has(div[data-testid="stNumberInput"]){
  flex: 0 0 92px !important;
  width: 92px !important;
  max-width: 92px !important;
}

.orivia-row div[data-testid="column"]:has(div[data-testid="stSelectbox"]){
  flex: 0 0 78px !important;
  width: 78px !important;
  max-width: 78px !important;
}

/* Widget 吃滿格子 */
.orivia-row div[data-testid="stNumberInput"],
.orivia-row div[data-testid="stSelectbox"]{
  width:100% !important;
}

/* number input 視覺 */
.orivia-row div[data-testid="stNumberInput"] input{
  padding: 6px 8px !important;
  font-size: 15px !important;
}

/* selectbox 視覺與文字 */
.orivia-row div[data-testid="stSelectbox"] div[data-baseweb="select"]{ width:100% !important; }
.orivia-row div[data-testid="stSelectbox"] div[role="combobox"]{
  padding: 6px 8px !important;
  font-size: 15px !important;
  min-height: 36px !important;
}
.orivia-row div[data-testid="stSelectbox"] span{
  white-space: nowrap !important;
  overflow: visible !important;
  text-overflow: clip !important;
}
.orivia-row div[data-testid="stSelectbox"] svg{
  width: 16px !important;
  height: 16px !important;
}

/* =========================
   ✅ Stepper 永久移除（你已驗證有效，再補強）
========================= */
div[data-testid="stNumberInput"] button{ display:none !important; }
div[data-testid="stNumberInput"] [data-baseweb="input"] button{ display:none !important; }
div[data-testid="stNumberInput"] svg{ display:none !important; }

/* =========================
   ✅ 最後保險：手機也不允許換行
========================= */
@media (max-width: 768px){
  .orivia-row div[data-testid="stHorizontalBlock"]{
    flex-direction: row !important;
    flex-wrap: nowrap !important;
  }
}
</style>
