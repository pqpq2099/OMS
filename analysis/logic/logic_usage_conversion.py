"""使用量換算邏輯模組。

外送平台銷售報表 → 配方展開 → 半成品拆解 → 包裝換算 → 顯示用 DataFrame。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_RECIPE_FILE = _DATA_DIR / "recipe_table.xlsx"

_SKIP_KEYWORDS = ["環保袋", "特色描述", "歡迎評價", "折價券", "官方會員", "註冊禮", "總計"]
_FILENAME_RE = re.compile(r"^report_(UberEats|foodpanda)_(\d{8})_(\d{8})\.xlsx$")


# ---------------------------------------------------------------------------
# 1. 報表解析
# ---------------------------------------------------------------------------

def parse_report_file(uploaded_file) -> dict[str, Any]:
    """解析上傳的外送平台報表，回傳 platform / date_range / items_df / error。"""
    name = uploaded_file.name
    m = _FILENAME_RE.match(name)
    if not m:
        return {"error": "檔名格式不符，請上傳 report_UberEats_xxx.xlsx 或 report_foodpanda_xxx.xlsx"}

    platform = m.group(1)
    date_start = f"{m.group(2)[:4]}/{m.group(2)[4:6]}/{m.group(2)[6:]}"
    date_end = f"{m.group(3)[:4]}/{m.group(3)[4:6]}/{m.group(3)[6:]}"
    date_range = f"{date_start} ~ {date_end}"

    df = pd.read_excel(uploaded_file, sheet_name=0, header=None)
    # Row 8+ = 品項資料
    if len(df) <= 8:
        return {"error": "報表內容不足，無法解析品項資料"}

    items = df.iloc[8:, :2].copy()
    items.columns = ["item_name", "qty"]
    items = items.dropna(subset=["item_name"])
    items["qty"] = pd.to_numeric(items["qty"], errors="coerce").fillna(0).astype(int)

    # 過濾非餐點
    mask = items["item_name"].apply(lambda x: not any(kw in str(x) for kw in _SKIP_KEYWORDS))
    items = items[mask].reset_index(drop=True)

    return {"platform": platform, "date_range": date_range, "items_df": items, "error": None}


# ---------------------------------------------------------------------------
# 2. 配方表讀取
# ---------------------------------------------------------------------------

def load_recipe_data() -> dict[str, pd.DataFrame] | None:
    """讀取配方表 Excel 的 4 個 sheet。找不到檔案或讀取失敗回傳 None。"""
    if not _RECIPE_FILE.exists():
        return None

    try:
        menu_items = pd.read_excel(_RECIPE_FILE, sheet_name="menu_items")
        aliases = pd.read_excel(_RECIPE_FILE, sheet_name="menu_item_aliases")
        recipes = pd.read_excel(_RECIPE_FILE, sheet_name="recipes")
        checklist = pd.read_excel(_RECIPE_FILE, sheet_name="items_checklist（需確認）", header=None)
    except Exception:
        return None

    # checklist 欄位對齊
    cl_headers = ["ingredient_name", "note", "confirm", "item_name", "pack_spec", "semi_recipe"]
    cl = checklist.iloc[1:].copy()
    cl.columns = cl_headers[: len(cl.columns)]
    # 補齊缺欄
    for h in cl_headers:
        if h not in cl.columns:
            cl[h] = ""
    cl = cl.fillna("").reset_index(drop=True)

    return {
        "menu_items": menu_items,
        "aliases": aliases,
        "recipes": recipes,
        "checklist": cl,
    }


# ---------------------------------------------------------------------------
# 3. 品名比對
# ---------------------------------------------------------------------------

def match_items(
    items_df: pd.DataFrame,
    platform: str,
    aliases: pd.DataFrame,
    menu_items: pd.DataFrame,
) -> tuple[list[dict], list[str]]:
    """品名比對：alias → menu_items.item_name_zh → unmatched。

    回傳 (matched_list, unmatched_names)。
    matched_list 每筆：{menu_item_id, item_name_zh, qty, recipe_required}
    """
    # 建 alias lookup: (platform, alias_name) → menu_item_id
    alias_map: dict[tuple[str, str], str] = {}
    for _, row in aliases.iterrows():
        alias_map[(row["platform"], row["alias_name"])] = row["menu_item_id"]

    # 建 name lookup: item_name_zh → menu_item_id
    name_map: dict[str, str] = {}
    for _, row in menu_items.iterrows():
        name_map[row["item_name_zh"]] = row["menu_item_id"]

    # menu_item_id → recipe_required
    req_map: dict[str, bool] = {}
    mi_name_map: dict[str, str] = {}
    for _, row in menu_items.iterrows():
        req_map[row["menu_item_id"]] = str(row["recipe_required"]).strip().lower() == "true"
        mi_name_map[row["menu_item_id"]] = row["item_name_zh"]

    matched: list[dict] = []
    unmatched: list[str] = []

    for _, row in items_df.iterrows():
        sale_name = str(row["item_name"]).strip()
        qty = int(row["qty"])
        if qty <= 0:
            continue

        # 1) alias
        mid = alias_map.get((platform, sale_name))
        # 2) direct name
        if mid is None:
            mid = name_map.get(sale_name)

        if mid is None:
            unmatched.append(sale_name)
            continue

        if not req_map.get(mid, False):
            # 飲料等不需換算
            continue

        matched.append({
            "menu_item_id": mid,
            "item_name_zh": mi_name_map.get(mid, sale_name),
            "qty": qty,
        })

    return matched, unmatched


# ---------------------------------------------------------------------------
# 4. 配方展開
# ---------------------------------------------------------------------------

def expand_recipes(
    matched: list[dict],
    recipes: pd.DataFrame,
) -> dict[str, dict]:
    """展開配方，回傳 {ingredient_name: {total_qty: float, unit: str}}。"""
    result: dict[str, dict] = {}

    for item in matched:
        mid = item["menu_item_id"]
        sale_qty = item["qty"]
        recs = recipes[recipes["menu_item_id"] == mid]

        for _, r in recs.iterrows():
            ing = str(r["ingredient_name"]).strip()
            qty = float(r["qty_per_serving"]) * sale_qty
            unit = str(r["unit"]).strip()

            if ing in result:
                result[ing]["total_qty"] += qty
            else:
                result[ing] = {"total_qty": qty, "unit": unit}

    return result


# ---------------------------------------------------------------------------
# 5. 半成品拆解
# ---------------------------------------------------------------------------

_SEMI_PART_RE = re.compile(r"^(.+?)([\d.]+)(g|kg|ml|L)$")


def _parse_semi_recipe(formula: str) -> list[dict]:
    """解析半成品配方字串，如 '明太子500g+鮭魚鬆200g'。"""
    parts = []
    for seg in formula.split("+"):
        seg = seg.strip()
        m = _SEMI_PART_RE.match(seg)
        if not m:
            continue
        name = m.group(1).strip()
        raw_qty = float(m.group(2))
        unit = m.group(3)
        # 統一為 g
        if unit == "kg":
            raw_qty *= 1000
        elif unit == "L":
            raw_qty *= 1000
        # ml = g (液體 1ml=1g)
        parts.append({"name": name, "qty_g": raw_qty})
    return parts


def resolve_semi_finished(
    ingredients: dict[str, dict],
    checklist: pd.DataFrame,
) -> dict[str, dict]:
    """拆解半成品，子原料合併到總表。"""
    # 找出哪些 ingredient 是半成品
    semi_map: dict[str, str] = {}
    for _, row in checklist.iterrows():
        recipe = str(row.get("semi_recipe", "")).strip()
        if recipe:
            semi_map[str(row["ingredient_name"]).strip()] = recipe

    resolved: dict[str, dict] = {}

    for ing, data in ingredients.items():
        if ing not in semi_map:
            # 非半成品，直接保留
            if ing in resolved:
                resolved[ing]["total_qty"] += data["total_qty"]
            else:
                resolved[ing] = {"total_qty": data["total_qty"], "unit": data["unit"]}
            continue

        # 半成品拆解
        parts = _parse_semi_recipe(semi_map[ing])
        if not parts:
            # 無法解析，保留原樣
            resolved[ing] = data
            continue

        batch_total = sum(p["qty_g"] for p in parts)
        if batch_total <= 0:
            resolved[ing] = data
            continue

        need_qty = data["total_qty"]  # g
        ratio = need_qty / batch_total

        for p in parts:
            sub_name = p["name"]
            if sub_name == "水":
                continue
            sub_qty = p["qty_g"] * ratio
            if sub_name in resolved:
                resolved[sub_name]["total_qty"] += sub_qty
            else:
                resolved[sub_name] = {"total_qty": sub_qty, "unit": "g"}

    return resolved


# ---------------------------------------------------------------------------
# 6. 包裝換算
# ---------------------------------------------------------------------------

# 品項名 → item_id（用於最終排序）
_ITEM_NAME_TO_ID: dict[str, str] = {
    "鮭魚鬆(500g/包)": "ING_000020",
    "元氣無骨雞排10片/包": "ING_000023",
    "呈冠帶殼溫泉蛋(10/盒)": "ING_000024",
    "北海道南瓜可樂餅60片/箱": "ING_000028",
    "義大利麵/熟(80包/箱)": "ING_000029",
    "青醬(1kg/包/)": "ING_000030",
    "辣肉醬(1kg/包)": "ING_000031",
    "強匠唐揚雞 1kg(包)": "ING_000035",
    "富統培根碎3kg(包)": "ING_000037",
    "台畜肉丸子1kg": "ING_000038",
    "麥斯鮮奶油 1L/12/箱": "ING_000079",
    "起司香腸(包)": "ING_000041",
    "急食鮮-紅醬": "ING_000042",
    "烹大師雞粉2kg(包)": "ING_000054",
    "蕃茄碎角Dailyfun(2500g)桶": "ING_000062",
    "CIRIO披薩蕃茄醬(2550g/罐)藍": "ING_000063",
    "精鹽-台鹽(1kg/包)": "ING_000065",
    "金福華玉米濃湯粉1kg": "ING_000066",
    "佳味珍美玉白汁3.5KG/盒": "ING_000068",
    "檸檬汁 1L/瓶": "ING_000069",
    "COCO義大利松露蘑菇醬500G/瓶": "ING_000072",
    "七味唐辛子小磨坊(300g/包)": "ING_000081",
    "特砂(1kg/包)": "ING_000082",
    "黑珍珠菇3kg/包": "ING_000086",
    "馬鈴薯丁1KG": "ING_000090",
    "蒜碎(1斤)600g": "ING_000092",
    "花椰菜1箱10包": "ING_000093",
    "鮭魚碎(1KG/包)": "ING_000094",
    "明太子(500g/包)": "ING_000095",
    "川廣牡蠣20PC": "ING_000096",
    "肌肉先生雞胸肉(120入/箱)": "ING_000097",
    "鹽酥杏鮑菇": "ING_000146",
}

# 半成品子原料的品項對照（子原料名 → 品項名, 包裝量g, 顯示單位）
_SEMI_SUB_ITEM_MAP: dict[str, tuple[str, float, str]] = {
    "明太子": ("明太子(500g/包)", 500, "包"),
    "佳味珍美玉白汁": ("佳味珍美玉白汁3.5KG/盒", 3500, "盒"),
    "檸檬汁": ("檸檬汁 1L/瓶", 1000, "瓶"),
    "七味粉": ("七味唐辛子小磨坊(300g/包)", 300, "包"),
    "鮭魚鬆": ("鮭魚鬆(500g/包)", 500, "包"),
    "鮭魚碎": ("鮭魚碎(1KG/包)", 1000, "包"),
    "蕃茄碎角": ("蕃茄碎角Dailyfun(2500g)桶", 2500, "桶"),
    "披薩蕃茄醬": ("CIRIO披薩蕃茄醬(2550g/罐)藍", 2550, "罐"),
    "紅醬": ("急食鮮-紅醬", 1500, "包"),
    "鹽巴": ("精鹽-台鹽(1kg/包)", 1000, "包"),
    "糖": ("特砂(1kg/包)", 1000, "包"),
    "玉米濃湯粉": ("金福華玉米濃湯粉1kg", 1000, "包"),
    "馬鈴薯丁": ("馬鈴薯丁1KG", 1000, "包"),
}

_PACK_QTY_RE = re.compile(r"([\d.]+)")


def _parse_pack_spec(spec: str, unit_hint: str) -> tuple[float, str]:
    """從包裝規格字串解析出包裝數量和單位。"""
    spec = str(spec).strip()
    if not spec:
        return 0, ""

    # 特殊：麵條 "一箱80包，每份1包"
    if "每份" in spec and "箱" in spec:
        m = re.search(r"(\d+)包/箱", spec)
        if not m:
            m = re.search(r"箱(\d+)包", spec)
        if not m:
            m = re.search(r"(\d+)包", spec)
        if m:
            return float(m.group(1)), "箱"

    # 雙層包裝："1箱6包，1包10片" → 取最小包裝單位
    if "，" in spec or "," in spec:
        sep = "，" if "，" in spec else ","
        parts = spec.split(sep)
        if len(parts) == 2:
            last_part = parts[1].strip()
            # "1包10片" → 取 10, 單位=包
            # "1包180g" → 取 180, 單位=包
            m_last = re.search(r"1[包罐盒](\d+)", last_part)
            if m_last:
                unit_char = re.search(r"1([包罐盒])", last_part)
                return float(m_last.group(1)), unit_char.group(1) if unit_char else "包"

    # 特殊："1箱120包，1包180g" → 取每包的數值
    if "箱" in spec and "g" in spec.lower():
        m = re.search(r"1包(\d+)g", spec, re.IGNORECASE)
        if m:
            return float(m.group(1)), "包"

    unit_chars = {"包": "包", "罐": "罐", "盒": "盒", "箱": "箱", "瓶": "瓶"}
    display_unit = ""
    for uc in unit_chars:
        if uc in spec:
            display_unit = uc
            break

    nums = _PACK_QTY_RE.findall(spec)
    if not nums:
        return 0, display_unit

    g_match = re.search(r"(\d+)\s*[克g]", spec, re.IGNORECASE)
    if g_match:
        return float(g_match.group(1)), display_unit

    return float(nums[-1]), display_unit


def convert_to_display(
    ingredients: dict[str, dict],
    checklist: pd.DataFrame,
) -> pd.DataFrame:
    """將原物料總用量換算成叫貨品項 + 包裝數量。

    回傳 DataFrame：item_name, display_qty, display_unit
    """
    # 建 checklist lookup
    cl_map: dict[str, dict] = {}
    for _, row in checklist.iterrows():
        ing = str(row["ingredient_name"]).strip()
        cl_map[ing] = {
            "item_name": str(row.get("item_name", "")).strip(),
            "pack_spec": str(row.get("pack_spec", "")).strip(),
            "note": str(row.get("note", "")).strip(),
        }

    rows = []
    for ing, data in ingredients.items():
        total = data["total_qty"]
        unit = data["unit"]

        # 先查 checklist
        cl = cl_map.get(ing, {})
        item_name = cl.get("item_name", "").strip()
        pack_spec = cl.get("pack_spec", "").strip()

        # 若 checklist 沒有，查半成品子原料 mapping
        if not item_name and ing in _SEMI_SUB_ITEM_MAP:
            mapped = _SEMI_SUB_ITEM_MAP[ing]
            item_name = mapped[0]
            convert_qty = mapped[1]
            display_unit = mapped[2]
            if convert_qty > 0:
                converted = total / convert_qty
                rows.append({
                    "item_name": item_name,
                    "display_qty": round(converted, 2),
                    "display_unit": display_unit,
                })
                continue

        if not item_name:
            item_name = ing

        if not pack_spec:
            rows.append({
                "item_name": item_name,
                "display_qty": round(total, 2),
                "display_unit": unit,
            })
            continue

        pack_qty, display_unit = _parse_pack_spec(pack_spec, unit)
        if pack_qty <= 0:
            rows.append({
                "item_name": item_name,
                "display_qty": round(total, 2),
                "display_unit": unit,
            })
            continue

        converted = total / pack_qty
        rows.append({
            "item_name": item_name,
            "display_qty": round(converted, 2),
            "display_unit": display_unit,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # 同品項合併（如青花菜 + 花椰菜 → 同一品項名）
    df = df.groupby(["item_name", "display_unit"], as_index=False)["display_qty"].sum()
    df["display_qty"] = df["display_qty"].round(2)

    # <0.01 隱藏
    df = df[df["display_qty"] >= 0.01]

    # 依 item_id 升序排序
    df["_sort_id"] = df["item_name"].map(_ITEM_NAME_TO_ID).fillna("ZZZ")
    df = df.sort_values("_sort_id").reset_index(drop=True)
    df = df.drop(columns=["_sort_id"])

    return df


# ---------------------------------------------------------------------------
# 7. 主流程
# ---------------------------------------------------------------------------

def process_report(uploaded_file) -> dict[str, Any]:
    """完整換算流程，回傳 page 層需要的所有資料。"""
    try:
        return _process_report_inner(uploaded_file)
    except Exception as e:
        return {"error": f"換算過程發生錯誤：{e}"}


def _process_report_inner(uploaded_file) -> dict[str, Any]:
    # 1. 解析報表
    parsed = parse_report_file(uploaded_file)
    if parsed.get("error"):
        return {"error": parsed["error"]}

    # 2. 讀取配方表
    recipe_data = load_recipe_data()
    if recipe_data is None:
        return {"error": "無法讀取配方表，請確認 data/recipe_table.xlsx 存在"}

    # 3. 品名比對
    matched, unmatched = match_items(
        parsed["items_df"],
        parsed["platform"],
        recipe_data["aliases"],
        recipe_data["menu_items"],
    )

    if not matched:
        return {
            "error": None,
            "platform": parsed["platform"],
            "date_range": parsed["date_range"],
            "sales_df": parsed["items_df"],
            "unmatched": unmatched,
            "result_df": pd.DataFrame(),
        }

    # 4. 配方展開
    ingredients = expand_recipes(matched, recipe_data["recipes"])

    # 5. 半成品拆解
    resolved = resolve_semi_finished(ingredients, recipe_data["checklist"])

    # 6. 包裝換算
    result_df = convert_to_display(resolved, recipe_data["checklist"])

    return {
        "error": None,
        "platform": parsed["platform"],
        "date_range": parsed["date_range"],
        "sales_df": parsed["items_df"],
        "unmatched": unmatched,
        "result_df": result_df,
    }
