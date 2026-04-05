# ============================================================
# ORIVIA OMS
# 檔案：pages/page_store_admin.py
# 說明：分店管理頁
# 功能：維護分店主檔與相關設定。
# 注意：此頁通常由 owner / admin 維護。
# ============================================================

from __future__ import annotations

import streamlit as st

from shared.utils.permissions import require_permission
from users_permissions.services.service_stores import StoreServiceError
from users_permissions.logic.store_admin import (
    build_store_admin_page_data,
    build_store_list_display_df,
    build_store_toggle_state,
    resolve_store_toggle_state,
    submit_create_store,
    submit_update_store_active,
)


def page_store_admin():
    st.title("🏬 分店管理")

    if not require_permission("system.store.manage"):
        return

    page_data = build_store_admin_page_data()
    stores_df = page_data["stores_df"]
    stores_view = page_data["stores_view"]

    tab1, tab2, tab3 = st.tabs([
        "分店列表",
        "新增分店",
        "啟用 / 停用",
    ])

    with tab1:
        st.subheader("分店列表")
        if stores_view.empty:
            st.info("目前尚無分店資料")
        else:
            show_df = build_store_list_display_df(stores_view)
            st.dataframe(show_df, use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("新增分店")
        brand_options = page_data["brand_options"]
        brand_label_map = page_data["brand_label_map"]
        _preview_store_code = page_data["preview_store_code"]

        with st.form("create_store_form"):
            if brand_options:
                brand_id = st.selectbox(
                    "品牌",
                    brand_options,
                    format_func=lambda x: brand_label_map.get(x, x),
                    key="store_admin_brand_id",
                )
            else:
                brand_id = st.text_input("品牌", key="store_admin_brand_id_fallback")

            store_name_zh = st.text_input(
                "中文分店名稱",
                key="store_admin_store_name_zh",
                help="例如：三總店",
            )
            st.caption("系統將自動建立分店代碼與系統名稱")
            submit_create = st.form_submit_button("建立分店")

        if submit_create:
            try:
                row = submit_create_store(
                    brand_id=str(brand_id).strip(),
                    store_name_zh=str(store_name_zh).strip(),
                )
                st.success(f"分店建立成功：{row.get('store_name_zh', '')}")
                st.rerun()
            except StoreServiceError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"建立失敗：{e}")

    with tab3:
        st.subheader("啟用 / 停用")

        if stores_view.empty:
            st.info("目前沒有可操作的分店資料")
        else:
            toggle_state = build_store_toggle_state(stores_view)
            selected_store_id = st.selectbox(
                "選擇分店",
                toggle_state["store_ids"],
                format_func=lambda x: toggle_state["option_map"].get(x, x),
                key="store_admin_select_store_id",
            )
            toggle_state = resolve_store_toggle_state(stores_view, selected_store_id)
            current_active = toggle_state["current_active"]

            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 啟用分店", use_container_width=True, key="store_admin_enable"):
                    try:
                        submit_update_store_active(
                            store_id=selected_store_id,
                            new_active=1,
                        )
                        st.success("分店已啟用")
                        st.rerun()
                    except StoreServiceError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"啟用失敗：{e}")

            with c2:
                if st.button("⛔ 停用分店", use_container_width=True, key="store_admin_disable"):
                    try:
                        submit_update_store_active(
                            store_id=selected_store_id,
                            new_active=0,
                        )
                        st.success("分店已停用")
                        st.rerun()
                    except StoreServiceError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"停用失敗：{e}")

            st.caption(f"目前狀態：{'啟用' if current_active == 1 else '停用'}")
