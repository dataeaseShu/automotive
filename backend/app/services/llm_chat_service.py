from __future__ import annotations

from typing import Any, Optional

from openai import AsyncOpenAI

from app.config import get_settings
from app.models.session import Session


_client: Optional[AsyncOpenAI] = None


def _get_client() -> Optional[AsyncOpenAI]:
    global _client
    settings = get_settings()
    if not settings.DASHSCOPE_API_KEY:
        return None
    if _client is None:
        try:
            _client = AsyncOpenAI(
                api_key=settings.DASHSCOPE_API_KEY,
                base_url=settings.DASHSCOPE_BASE_URL,
            )
        except Exception:
            return None
    return _client


async def chat_with_llm(session: Session, text: str) -> str:
    client = _get_client()
    if client is None:
        return "我收到了。您可以继续描述需求；如果是汽车投放计划，请直接说车型、预算、目标和地域。"

    settings = get_settings()

    history: list[dict[str, Any]] = []
    for msg in session.messages[-8:]:
        if msg.role not in {"user", "assistant"}:
            continue
        if not isinstance(msg.content, str):
            continue
        history.append({"role": msg.role, "content": msg.content})

    prompt_messages = [
        {
            "role": "system",
            "content": (
                "你是一个简洁、专业的中文助手。"
                "当用户在讨论汽车营销投放时，提醒其可继续给出更完整约束（车型/预算/目标/地域）。"
            ),
        },
        *history,
        {"role": "user", "content": text},
    ]

    try:
        resp = await client.chat.completions.create(
            model=settings.DASHSCOPE_MODEL,
            messages=prompt_messages,
            temperature=0.3,
            top_p=0.8,
        )
        content = (resp.choices[0].message.content or "").strip()
        return content or "我收到了，请继续补充。"
    except Exception:
        return "我收到了。您可以继续描述需求；如果是汽车投放计划，请直接说车型、预算、目标和地域。"
