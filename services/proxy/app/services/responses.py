from datetime import datetime
import json

from fastapi import HTTPException

from app.prompts.dispatcher import get_system_prompt
from app.services.send_to_anthropic import send_to_anthropic
from app.services.send_to_openai_responses import send_to_openai_responses
from app.services.util import _resolve_model_provider_options
from shared.log_config import get_logger
from shared.models.prompt import BuildSystemPrompt
from shared.models.proxy import AnthropicRequest, ProxyResponse, ResponsesRequest

logger = get_logger(f"proxy.{__name__}")


def _extract_content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type in {"input_text", "output_text", "text"} and item.get("text"):
                parts.append(item["text"])
        return "\n".join(part for part in parts if part)
    return ""


def _normalize_input_messages(input_data) -> list[dict]:
    if isinstance(input_data, str):
        return [{"role": "user", "content": input_data}]

    messages = []
    for item in input_data:
        if not isinstance(item, dict):
            continue

        if item.get("type") == "message":
            role = item.get("role", "user")
            content = _extract_content_text(item.get("content"))
            messages.append({"role": role, "content": content})
            continue

        if item.get("role"):
            messages.append({
                "role": item["role"],
                "content": _extract_content_text(item.get("content")),
            })

    return messages
async def _responses(request: ResponsesRequest) -> ProxyResponse:
    logger.debug(f"/api/responses Request:\n{json.dumps(request.model_dump(), indent=4, ensure_ascii=False)}")

    provider, actual_model, options = _resolve_model_provider_options(request.model)
    logger.debug(f"Resolved provider/model/options: {provider}, {actual_model}, {options}")

    system_prompt = get_system_prompt(
        BuildSystemPrompt(
            mode=request.model or "default",
            platform="api",
            timestamp=datetime.now().isoformat(timespec="seconds"),
            agent_prompt=request.agent_prompt or None,
        ),
        provider=provider,
        mode=request.model or "default",
    )
    tool_choice = "auto" if request.tools else None

    if provider == "ollama":
        raise HTTPException(
            status_code=400,
            detail="Responses endpoint does not support provider 'ollama'. Use /api/singleturn or /api/multiturn for now.",
        )

    if provider == "openai":
        result = await send_to_openai_responses(
            model=actual_model,
            input_data=request.input,
            instructions=system_prompt,
            options=options,
            tools=request.tools,
            tool_choice=tool_choice,
        )
    elif provider == "anthropic":
        messages = _normalize_input_messages(request.input)
        anthropic_messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + messages
        payload = AnthropicRequest(
            model=actual_model,
            messages=anthropic_messages,
            options=options,
            tools=request.tools,
            tool_choice=tool_choice,
        )
        result = await send_to_anthropic(payload)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    return ProxyResponse(
        response=getattr(result, "response", None),
        eval_count=getattr(result, "eval_count", None),
        prompt_eval_count=getattr(result, "prompt_eval_count", None),
        tool_calls=getattr(result, "tool_calls", None),
        function_call=getattr(result, "function_call", None),
        timestamp=datetime.now().isoformat(),
    )
