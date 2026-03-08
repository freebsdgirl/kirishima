from __future__ import annotations

from dataclasses import dataclass
import json
from uuid import uuid4
from typing import Any

import httpx


@dataclass(frozen=True)
class ChatUsage:
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True)
class ChatResult:
    text: str
    usage: ChatUsage


@dataclass(frozen=True)
class AdminError:
    code: int
    message: str
    data: dict[str, Any] | None = None


class AdminRpcError(RuntimeError):
    def __init__(self, code: int, message: str, data: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data or None


@dataclass(frozen=True)
class LedgerMessage:
    id: int
    role: str
    content: str
    tool_calls: dict[str, Any] | None
    function_call: dict[str, Any] | None
    tool_call_id: str | None
    created_at: str
    model: str | None


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


class LedgerClient:
    def __init__(self, ledger_base_url: str, user_id: str):
        self._base_url = ledger_base_url.rstrip("/")
        self._user_id = user_id

    async def get_recent_messages(self) -> list[LedgerMessage]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(f"{self._base_url}/sync/get")
            response.raise_for_status()
            payload = response.json()
        return [_to_ledger_message(item) for item in payload]

    async def get_history_turns(self, turns: int = 15) -> list[LedgerMessage]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{self._base_url}/user/{self._user_id}/messages",
                params={"turns": turns},
            )
            response.raise_for_status()
            payload = response.json()
        return [_to_ledger_message(item) for item in payload]

    async def stream_messages(self, poll_ms: int = 250, heartbeat_s: int = 15):
        params = {"poll_ms": poll_ms, "heartbeat_s": heartbeat_s}
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", f"{self._base_url}/user/stream", params=params) as response:
                response.raise_for_status()
                event_name: str | None = None
                data_lines: list[str] = []
                async for line in response.aiter_lines():
                    if line == "":
                        if event_name and data_lines:
                            yield event_name, "\n".join(data_lines)
                        event_name = None
                        data_lines = []
                        continue
                    if line.startswith(":"):
                        continue
                    if line.startswith("event:"):
                        event_name = line.split(":", 1)[1].strip()
                        continue
                    if line.startswith("data:"):
                        data_lines.append(line.split(":", 1)[1].lstrip())
                        continue


class AdminClient:
    def __init__(self, brain_base_url: str):
        self._base_url = brain_base_url.rstrip("/")

    async def send_admin(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = str(uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(f"{self._base_url}/admin/rpc", json=payload)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Admin RPC request failed: {exc}") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Admin RPC HTTP error: {exc.response.status_code} {exc.response.text}"
            ) from exc

        try:
            rpc_response = response.json()
        except ValueError as exc:
            raise RuntimeError("Admin RPC returned invalid JSON.") from exc

        if rpc_response.get("jsonrpc") != "2.0":
            raise RuntimeError("Admin RPC returned an invalid protocol response.")
        if rpc_response.get("id") != request_id:
            raise RuntimeError("Admin RPC response ID did not match the request.")

        error = rpc_response.get("error")
        if isinstance(error, dict):
            raise AdminRpcError(
                code=int(error.get("code", -32603)),
                message=str(error.get("message") or "Admin RPC error"),
                data=error.get("data") if isinstance(error.get("data"), dict) else None,
            )

        result = rpc_response.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("Admin RPC returned a non-object result.")
        return result


def _to_ledger_message(payload: dict[str, Any]) -> LedgerMessage:
    tool_calls = payload.get("tool_calls")
    if isinstance(tool_calls, str):
        try:
            tool_calls = json.loads(tool_calls)
        except Exception:
            tool_calls = None
    function_call = payload.get("function_call")
    if isinstance(function_call, str):
        try:
            function_call = json.loads(function_call)
        except Exception:
            function_call = None

    return LedgerMessage(
        id=int(payload.get("id", 0)),
        role=str(payload.get("role", "")),
        content=str(payload.get("content") or ""),
        tool_calls=tool_calls if isinstance(tool_calls, dict) else None,
        function_call=function_call if isinstance(function_call, dict) else None,
        tool_call_id=payload.get("tool_call_id"),
        created_at=str(payload.get("created_at") or ""),
        model=payload.get("model"),
    )
