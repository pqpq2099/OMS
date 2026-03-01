elif st.session_state.step == "view_history":
    st.title(f"📜 {st.session_state.store} 歷史紀錄庫")
    view_df = st.session_state.get('view_df', pd.DataFrame())
    
    if not view_df.empty:
        # 建立兩個分頁：明細與趨勢
        tab1, tab2 = st.tabs(["📋 數據明細", "📈 消耗趨勢"])
        
        with tab1:
            search = st.text_input("🔍 搜尋品項或日期")
            display_df = view_df.copy()
            if search:
                display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search)).any(axis=1)]
            st.dataframe(display_df.sort_values('日期', ascending=False), use_container_width=True, hide_index=True)
        
        with tab2:
            if HAS_PLOTLY:
                # 讓使用者選擇要分析的品項
                all_items = sorted(view_df['品項名稱'].unique())
                target_item = st.selectbox("請選擇分析品項", options=all_items)
                
                # 過濾該品項數據
                chart_df = view_df[view_df['品項名稱'] == target_item].copy()
                
                # 💡 核心修正：強制轉換日期格式，徹底移除時間與毫秒
                chart_df['日期'] = pd.to_datetime(chart_df['日期']).dt.strftime('%Y-%m-%d')
                chart_df = chart_df.sort_values('日期')
                
                # 繪製線圖
                fig = px.line(
                    chart_df, 
                    x="日期", 
                    y="期間消耗", 
                    title=f"【{target_item}】消耗走勢",
                    markers=True,
                    text="期間消耗" # 在點上直接顯示數值
                )
                
                # 最佳化圖表樣式
                fig.update_traces(textposition="top center", line_color='#1f77b4', line_width=3)
                fig.update_layout(
                    xaxis_type='category', # 強制分類軸，避免時間軸自動產生雜訊
                    hovermode="x unified",
                    margin=dict(l=10, r=10, t=50, b=10),
                    font=dict(family="PingFang TC, Microsoft JhengHei", size=12)
                )
                
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            else:
                st.warning("⚠️ 系統偵測不到繪圖引擎，請確認已安裝 plotly")

    if st.button("⬅️ 返回廠商列表", use_container_width=True):
        st.session_state.step = "select_vendor"
        st.rerun()
