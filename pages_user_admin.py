import streamlit as st


def page_user_admin():

    st.title("👥 使用者權限")

    tab1, tab2, tab3 = st.tabs([
        "使用者列表",
        "店長管理",
        "組長管理"
    ])

    # -------------------------
    # 使用者列表
    # -------------------------
    with tab1:

        st.subheader("使用者列表")

        st.info("之後會顯示 users 資料表")

        if st.button("新增使用者"):
            st.write("新增使用者表單（未完成）")

    # -------------------------
    # 店長管理
    # -------------------------
    with tab2:

        st.subheader("店長管理")

        st.info("Admin 可以指派店長 → 分店")

    # -------------------------
    # 組長管理
    # -------------------------
    with tab3:

        st.subheader("組長管理")

        st.info("店長可以指派組長")
