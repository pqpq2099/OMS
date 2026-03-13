"""
頁面模組：分店管理

功能：
1. 顯示分店列表
2. 新增分店
3. 啟用 / 停用分店

資料來源：
Google Sheet
- stores
- brands
- id_sequences

設計原則：
1. 沿用目前 OMS 既有架構
2. 統一使用 oms_core 的 read_table / append_rows_by_header / get_header / allocate_ids
3. 不另外建立新模組
4. 新增分店時，只輸入品牌與中文分店名稱
5. store_id / store_code / store_name 由系統自動產生
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from oms_core import (
    read_table,
    append_rows_by_header,
    get_header,
    allocate_ids,
    get_spreadsheet,
    bust_cache,
)


# ============================================================
# [S1] 基礎欄位安全處理
# ============================================================
def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """確保 DataFrame 至少有指定欄位，不足時自動補空字串。"""
    work = df.copy()
    for col in columns:
        if col not in work.columns:
            work[col] = ""
    return work


def _pick_first_existing_column(df: pd.DataFrame, candidates: list[str], fallback: str) -> str:
    """從候選欄位中挑第一個存在的欄位。"""
    for col in candidates:
        if col in df.columns:
            return col
    return fallback


def _safe_active_series(df: pd.DataFrame, col: str = "is_active") -> pd.Series:
    """將 is_active 轉成 1/0，空值預設為 1。"""
    if col not in df.columns:
        return pd.Series([1] * len(df), index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(1).astype(int)


# ============================================================
# [S2] 將整張 stores 表寫回 Google Sheet
# 用於啟用 / 停用更新
# ============================================================
def _write_back_stores_df(stores_df: pd.DataFrame):
    """將整理後的 stores_df 依原 header 寫回 Google Sheet。"""
    stores_header = get_header("stores")
    work = stores_df.copy()

    for col in stores_header:
        if col not in work.columns:
            work[col] = ""

    work = work[stores_header].copy()

    rows = [stores_header] + work.fillna("").astype(str).values.tolist()

    sh = get_spreadsheet()
    if sh is None:
        raise ValueError("Spreadsheet 未初始化")

    ws = sh.worksheet("stores")
    ws.clear()
    ws.update(rows)
    bust_cache()


# ============================================================
# [S3] 更新單一分店啟用狀態
# ============================================================
def _update_store_active(store_id: str, new_active: int, actor: str = "system"):
    """更新指定 store_id 的 is_active。"""
    stores_df = read_table("stores")
    if stores_df.empty:
        raise ValueError("stores 表沒有資料")

    stores_df = _ensure_columns(
        stores_df,
        [
            "store_id",
            "brand_id",
            "store_name",
            "store_name_zh",
            "store_code",
            "is_active",
            "created_at",
            "updated_at",
            "updated_by",
        ],
    )

    mask = stores_df["store_id"].astype(str).str.strip() == str(store_id).strip()

    if not mask.any():
        raise ValueError(f"找不到分店：{store_id}")

    stores_df.loc[mask, "is_active"] = int(new_active)

    if "updated_at" in stores_df.columns:
        stores_df.loc[mask, "updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if "updated_by" in stores_df.columns:
        stores_df.loc[mask, "updated_by"] = actor

    _write_back_stores_df(stores_df)


# ============================================================
# [S4] 自動產生下一個 store_code
# 規則：
# 已存在 S001 ~ S999 時，取下一個可用值
# ============================================================
def _generate_next_store_code(stores_df: pd.DataFrame) -> str:
    """依現有 store_code 自動產生下一個 S###。"""
    if stores_df.empty or "store_code" not in stores_df.columns:
        return "S001"

    codes = (
        stores_df["store_code"]
        .astype(str)
        .str.strip()
        .str.upper()
        .tolist()
    )

    used_numbers = []
    for code in codes:
        if code.startswith("S") and len(code) >= 2:
            num_part = code[1:]
            if num_part.isdigit():
                used_numbers.append(int(num_part))

    next_num = 1 if not used_numbers else max(used_numbers) + 1
    return f"S{next_num:03d}"


# ============================================================
# [S5] 主頁：分店管理
# ============================================================
def page_store_admin():
    st.title("🏬 分店管理")

    # --------------------------------------------------------
    # 權限限制：只有 owner / admin 可進入
    # --------------------------------------------------------
    role = st.session_state.get("role", "")
    if role not in ["owner", "admin"]:
        st.error("你沒有權限進入此頁。")
        return

    # --------------------------------------------------------
    # 讀取資料表
    # --------------------------------------------------------
    stores_df = read_table("stores")
    brands_df = read_table("brands")

    if stores_df.empty:
        stores_df = pd.DataFrame(columns=[
            "store_id",
            "brand_id",
            "store_name",
            "store_name_zh",
            "store_code",
            "is_active",
            "created_at",
            "updated_at",
            "updated_by",
        ])

    stores_df = _ensure_columns(
        stores_df,
        [
            "store_id",
            "brand_id",
            "store_name",
            "store_name_zh",
            "store_code",
            "is_active",
            "created_at",
            "updated_at",
            "updated_by",
        ],
    )

    brands_df = _ensure_columns(
        brands_df,
        [
            "brand_id",
            "brand_name",
            "brand_name_zh",
            "is_active",
        ],
    )

    # --------------------------------------------------------
    # 型別整理
    # --------------------------------------------------------
    stores_df["store_id"] = stores_df["store_id"].astype(str).str.strip()
    stores_df["brand_id"] = stores_df["brand_id"].astype(str).str.strip()
    stores_df["store_name"] = stores_df["store_name"].astype(str).str.strip()
    stores_df["store_name_zh"] = stores_df["store_name_zh"].astype(str).str.strip()
    stores_df["store_code"] = stores_df["store_code"].astype(str).str.strip().str.upper()
    stores_df["is_active"] = _safe_active_series(stores_df)

    brands_df["brand_id"] = brands_df["brand_id"].astype(str).str.strip()
    brands_df["brand_name"] = brands_df["brand_name"].astype(str).str.strip()
    brands_df["brand_name_zh"] = brands_df["brand_name_zh"].astype(str).str.strip()
    brands_df["is_active"] = _safe_active_series(brands_df)

    # --------------------------------------------------------
    # 品牌顯示名稱
    # --------------------------------------------------------
    brand_label_col = _pick_first_existing_column(
        brands_df,
        ["brand_name_zh", "brand_name"],
        "brand_id",
    )

    brand_map = brands_df[["brand_id", brand_label_col]].copy()
    brand_map = brand_map.rename(columns={brand_label_col: "brand_display"})

    # --------------------------------------------------------
    # 顯示用分店表
    # --------------------------------------------------------
    stores_view = stores_df.merge(
        brand_map,
        on="brand_id",
        how="left",
    )

    stores_view["brand_display"] = stores_view["brand_display"].fillna(stores_view["brand_id"])
    stores_view["store_display"] = stores_view["store_name_zh"].replace("", pd.NA).fillna(stores_view["store_name"])
    stores_view["status_text"] = stores_view["is_active"].map({1: "啟用", 0: "停用"}).fillna("未設定")

    stores_view = stores_view.sort_values(
        by=["store_code", "store_id"],
        ascending=[True, True],
        na_position="last",
    ).reset_index(drop=True)

    # --------------------------------------------------------
    # 三個分頁
    # --------------------------------------------------------
    tab1, tab2, tab3 = st.tabs([
        "分店列表",
        "新增分店",
        "啟用 / 停用",
    ])

    # ========================================================
    # TAB 1 分店列表
    # ========================================================
    with tab1:
        st.subheader("分店列表")

        if stores_view.empty:
            st.info("目前尚無分店資料")
        else:
            show_df = stores_view[
                ["store_id", "store_code", "store_display", "brand_display", "status_text"]
            ].copy()

            show_df.columns = [    
                "分店名稱",
                "品牌",
                "狀態",
            ]

            st.dataframe(show_df, use_container_width=True, hide_index=True)

    # ========================================================
    # TAB 2 新增分店
    # ========================================================
    with tab2:
        st.subheader("新增分店")

        active_brands_df = brands_df[brands_df["is_active"] == 1].copy()

        brand_options = (
            active_brands_df["brand_id"]
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .tolist()
        )

        brand_label_map = (
            active_brands_df.set_index("brand_id")[brand_label_col].to_dict()
            if not active_brands_df.empty and brand_label_col in active_brands_df.columns
            else {}
        )

        # 先預覽下一個代碼，讓使用者知道系統會自動生成
        preview_store_code = _generate_next_store_code(stores_df)

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

            st.caption(f"系統將自動產生分店代碼：{preview_store_code}")
            st.caption("系統名稱將自動與中文分店名稱相同")

            submit_create = st.form_submit_button("建立分店")

        if submit_create:
            brand_id = str(brand_id).strip()
            store_name_zh = str(store_name_zh).strip()

            if not brand_id:
                st.error("品牌不可為空")
                return

            if not store_name_zh:
                st.error("中文分店名稱不可為空")
                return

            # 中文分店名稱避免重複
            existing_store_name_zh = (
                stores_df["store_name_zh"]
                .astype(str)
                .str.strip()
                .tolist()
            )
            if store_name_zh in existing_store_name_zh:
                st.error("中文分店名稱已存在，請確認是否重複建立")
                return

            # 依 id_sequences 產生 store_id
            new_store_id = allocate_ids({"stores": 1})["stores"][0]

            # 自動產生 store_code
            new_store_code = _generate_next_store_code(stores_df)

            # 系統名稱自動跟中文走
            new_store_name = store_name_zh

            new_row = {
                "store_id": new_store_id,
                "brand_id": brand_id,
                "store_name": new_store_name,
                "store_name_zh": store_name_zh,
                "store_code": new_store_code,
                "is_active": 1,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": "",
                "updated_by": "",
            }

            stores_header = get_header("stores")
            append_rows_by_header("stores", stores_header, [new_row])

            st.success(f"分店建立成功：{store_name_zh}（{new_store_id} / {new_store_code}）")
            st.rerun()

    # ========================================================
    # TAB 3 啟用 / 停用
    # ========================================================
    with tab3:
        st.subheader("啟用 / 停用")

        if stores_view.empty:
            st.info("目前沒有可操作的分店資料")
        else:
            option_map = {}
            for _, row in stores_view.iterrows():
                sid = str(row.get("store_id", "")).strip()
                scode = str(row.get("store_code", "")).strip()
                sname = str(row.get("store_display", "")).strip()
                status_text = str(row.get("status_text", "")).strip()
                option_map[sid] = f"{sname}（{scode} / {sid} / {status_text}）"

            store_ids = list(option_map.keys())

            selected_store_id = st.selectbox(
                "選擇分店",
                store_ids,
                format_func=lambda x: option_map.get(x, x),
                key="store_admin_select_store_id",
            )

            current_row = stores_view[stores_view["store_id"] == selected_store_id].copy()
            current_active = 1
            if not current_row.empty:
                current_active = int(current_row.iloc[0]["is_active"])

            c1, c2 = st.columns(2)

            with c1:
                if st.button("✅ 啟用分店", use_container_width=True, key="store_admin_enable"):
                    try:
                        _update_store_active(
                            store_id=selected_store_id,
                            new_active=1,
                            actor=st.session_state.get("role", "system"),
                        )
                        st.success("分店已啟用")
                        st.rerun()
                    except Exception as e:
                        st.error(f"啟用失敗：{e}")

            with c2:
                if st.button("⛔ 停用分店", use_container_width=True, key="store_admin_disable"):
                    try:
                        _update_store_active(
                            store_id=selected_store_id,
                            new_active=0,
                            actor=st.session_state.get("role", "system"),
                        )
                        st.success("分店已停用")
                        st.rerun()
                    except Exception as e:
                        st.error(f"停用失敗：{e}")

            st.caption(f"目前狀態：{'啟用' if current_active == 1 else '停用'}")
