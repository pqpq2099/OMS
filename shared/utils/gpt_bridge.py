# ============================================================
# shared/utils/gpt_bridge.py
# 說明：Claude 呼叫 ChatGPT 的橋接工具
# 用途：讓 Claude Code 在需要第二意見或特定任務時呼叫 GPT-4o
# ============================================================

from __future__ import annotations

import os
import requests
from pathlib import Path


# ----------------------------------------------------------
# 使用者個人化系統提示（對應 ChatGPT 長期記憶 + 自訂指令）
# ----------------------------------------------------------
_USER_SYSTEM_PROMPT = """
你是一位高結構系統顧問，同時具備架構設計、教學轉化、現場落地三種能力。
請用繁體中文回答，口語但精準，偏實務、偏現場。

【使用者背景】
- 身份：系統設計者（由餐飲業轉型）
- 核心能力：高結構 × 高覺察 × 高應用，擅長現場邏輯、人性觀察、制度模組化、訓練架構設計
- 工作目標：建立「可落地、可教學、可複製」的系統與流程
- 不懂程式碼，討厭流程反覆變動，需要穩定一致的指引

【主要專案：OMS（Operation Decision System）】
- 定位：決策支援系統（非 ERP、非財務系統）
- 核心用途：協助叫貨決策、提供數量判斷依據、作為訓練工具
- 流程範圍：盤點 → 建立 PO → 確認 PO → 指定 delivery_date（不含收貨/驗收/退貨）
- 關鍵定義：「儲存並同步」= 建立訂單；「發送到 LINE」= 最終確認（唯一確認點）
- 架構分層：pages（UI）→ logic（流程）→ services（資料）→ shared（共用）
- UI 不做計算、不做驗證、不寫資料
- 所有清單固定依 item_id 排序，不可變動
- 日期規則：operation_date（庫存主軸）/ delivery_date（叫貨明細）/ order_created_date（寫入時間）

【回答規則】
格式：
- 條列式優先，分層結構（大標 → 中標 → 細項）
- 先大方向 → 再分類 → 再細節
- 可直接複製使用

內容：
- 不要冗長廢話，不要模糊建議
- 要：清楚結論、明確步驟、可執行
- 高結構 × 高效率 × 可落地，模組化輸出

禁止：
- 輸出難懂的程式操作說明
- 每次講法不一致
- 無結構回答、過度發散建議
- 改變使用者既有規則
""".strip()


# ----------------------------------------------------------
# 內部工具
# ----------------------------------------------------------

def _load_api_key() -> str:
    """從 .env 讀取 OPENAI_API_KEY。"""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip()
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise EnvironmentError("找不到 OPENAI_API_KEY，請確認 .env 檔案存在")
    return key


def _call(
    messages: list[dict],
    model: str,
    max_tokens: int,
) -> str:
    """底層 API 呼叫。"""
    api_key = _load_api_key()
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        },
        timeout=60,
    )
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"OpenAI API 錯誤：{data['error']['message']}")
    return data["choices"][0]["message"]["content"].strip()


# ----------------------------------------------------------
# 公開 API
# ----------------------------------------------------------

def ask_gpt(
    prompt: str,
    system: str | None = None,
    model: str = "gpt-4o-mini",
    max_tokens: int = 1000,
    use_user_context: bool = True,
) -> str:
    """
    呼叫 ChatGPT 並回傳純文字結果。

    Parameters
    ----------
    prompt : str
        要問 ChatGPT 的內容
    system : str | None
        自訂系統提示。None 時使用使用者個人化提示（_USER_SYSTEM_PROMPT）
    model : str
        使用的模型，預設 gpt-4o-mini（省 token）；需要更強時用 gpt-4o
    max_tokens : int
        回應最大 token 數
    use_user_context : bool
        是否套用使用者個人化背景（預設 True）
    """
    if system is None:
        system = _USER_SYSTEM_PROMPT if use_user_context else "你是一個專業助手，請用繁體中文回答。"

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    return _call(messages, model, max_tokens)


def code_review(code: str, context: str = "") -> str:
    """請 GPT-4o 做程式碼 review（使用技術型系統提示，不套用使用者個人背景）。"""
    system = (
        "你是一位資深 Python 工程師，專注於程式碼品質、可維護性與架構合理性。"
        "請用繁體中文條列式回答，每點簡短精確。"
    )
    prompt = f"""請 review 以下程式碼，指出潛在問題、可讀性問題或改善建議。

背景說明：{context if context else '無'}

程式碼：
```python
{code}
```"""
    return ask_gpt(prompt, system=system, model="gpt-4o", use_user_context=False)


def second_opinion(topic: str, my_decision: str) -> str:
    """
    對某個技術決策請 GPT 提供第二意見。
    適合用於：架構選擇、流程設計、規則制定。
    """
    prompt = f"""以下是我對一個技術問題的決策，請給我第二意見：

【主題】
{topic}

【我的決策】
{my_decision}

請條列式回答：
1. 這個決策的優點
2. 潛在風險或盲點
3. 如果你來做，會有什麼不同？（若無則說明同意原決策）"""
    return ask_gpt(prompt, model="gpt-4o")


def translate_to_en(text: str) -> str:
    """將繁體中文翻譯為英文（適合 commit message、文件等）。"""
    system = "You are a professional technical translator. Translate accurately, preserving technical terms."
    return ask_gpt(
        f"Translate the following Traditional Chinese to professional English:\n\n{text}",
        system=system,
        model="gpt-4o-mini",
        use_user_context=False,
    )


def summarize(text: str, max_lines: int = 10) -> str:
    """摘要長文字為條列重點。"""
    prompt = f"請將以下內容摘要為最多 {max_lines} 行的繁體中文條列重點，每點一句話：\n\n{text}"
    return ask_gpt(prompt, model="gpt-4o-mini")


def design_module(requirement: str) -> str:
    """
    給需求，請 GPT 設計模組架構或流程。
    適合用於：新功能規劃、訓練架構設計、制度模組化。
    """
    prompt = f"""請根據以下需求，設計一個可落地、可教學、可複製的模組架構：

【需求】
{requirement}

請輸出：
1. 模組名稱與定位
2. 核心流程（條列）
3. 各角色責任（若適用）
4. 注意事項與限制"""
    return ask_gpt(prompt, model="gpt-4o", max_tokens=1500)
