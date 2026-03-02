from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChatUsage:
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True)
class ChatResult:
    text: str
    usage: ChatUsage


class ChatClient:
    def __init__(self, api_base_url: str):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency: openai. Install with './.venv/bin/pip install openai'."
            ) from exc

        self._client = OpenAI(
            base_url=api_base_url.rstrip("/"),
            api_key="not-needed",
        )

    def send_chat(self, message: str, model: str) -> ChatResult:
        response = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": message}],
        )

        content = ""
        if response.choices:
            content = _normalize_content(response.choices[0].message.content)

        usage = ChatUsage(
            prompt_tokens=getattr(response.usage, "prompt_tokens", None),
            completion_tokens=getattr(response.usage, "completion_tokens", None),
            total_tokens=getattr(response.usage, "total_tokens", None),
        )
        return ChatResult(text=content, usage=usage)


def _normalize_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            else:
                text = getattr(item, "text", None)
                if text:
                    parts.append(str(text))
        return "\n".join(parts).strip()
    return str(content)
