# ============================================================
# shared/utils/gpt_bridge.py
# 說明：Claude 呼叫 ChatGPT 的橋接工具
# 用途：讓 Claude Code 在需要第二意見或特定任務時呼叫 GPT-4o
# ============================================================

from __future__ import annotations

import os
import requests
from pathlib import Path


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


def ask_gpt(
    prompt: str,
    system: str = "你是一個專業的軟體工程師，請用繁體中文回答。",
    model: str = "gpt-4o-mini",
    max_tokens: int = 1000,
) -> str:
    """
    呼叫 ChatGPT 並回傳純文字結果。

    Parameters
    ----------
    prompt : str
        要問 ChatGPT 的內容
    system : str
        系統提示（角色設定）
    model : str
        使用的模型，預設 gpt-4o-mini（省 token）；需要更強時用 gpt-4o
    max_tokens : int
        回應最大 token 數

    Returns
    -------
    str
        ChatGPT 的回應文字
    """
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
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=60,
    )

    data = resp.json()

    if "error" in data:
        raise RuntimeError(f"OpenAI API 錯誤：{data['error']['message']}")

    return data["choices"][0]["message"]["content"].strip()


def code_review(code: str, context: str = "") -> str:
    """請 ChatGPT 做程式碼 review。"""
    prompt = f"""請 review 以下程式碼，指出潛在問題、可讀性問題、或改善建議。

背景說明：{context if context else '無'}

程式碼：
```python
{code}
```

請條列式回答，每點簡短說明。"""
    return ask_gpt(prompt, model="gpt-4o")


def translate_to_en(text: str) -> str:
    """將繁體中文翻譯為英文（適合 commit message、文件等）。"""
    return ask_gpt(
        f"請將以下繁體中文翻譯為專業的英文，保留技術術語：\n\n{text}",
        system="You are a professional technical translator.",
        model="gpt-4o-mini",
    )


def summarize(text: str, max_lines: int = 10) -> str:
    """摘要長文字。"""
    return ask_gpt(
        f"請將以下內容摘要為最多 {max_lines} 行的繁體中文重點整理：\n\n{text}",
        model="gpt-4o-mini",
    )
