import json

import httpx
from fastapi import HTTPException, status

from shared.log_config import get_logger
from shared.models.proxy import OpenAIResponse

logger = get_logger(f"proxy.{__name__}")


def _normalize_response_input(input_data):
    if isinstance(input_data, str):
        return input_data

    normalized = []
    for item in input_data:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            normalized.append(item)
            continue

        if "role" in item:
            content = item.get("content", "")
            if isinstance(content, str):
                content = [{"type": "input_text", "text": content}]
            normalized.append({
                "type": "message",
                "role": item["role"],
                "content": content,
            })

    return normalized


def _normalize_tools(tools):
    if not tools:
        return None

    normalized = []
    for tool in tools:
        if tool.get("type") == "function" and tool.get("function"):
            function = tool["function"]
            normalized.append({
                "type": "function",
                "name": function.get("name"),
                "description": function.get("description"),
                "parameters": function.get("parameters", {}),
            })
        else:
            normalized.append(tool)
    return normalized


def _normalize_options(options):
    normalized = dict(options or {})
    if "max_tokens" in normalized and "max_output_tokens" not in normalized:
        normalized["max_output_tokens"] = normalized.pop("max_tokens")
    return normalized


async def send_to_openai_responses(
    *,
    model: str,
    input_data,
    instructions: str | None,
    options: dict | None,
    tools=None,
    tool_choice: str | None = None,
) -> OpenAIResponse:
    normalized_input = _normalize_response_input(input_data)
    normalized_tools = _normalize_tools(tools)
    normalized_options = _normalize_options(options)

    logger.debug(
        "🤖 Request to OpenAI Responses API:\n%s",
        json.dumps(
            {
                "model": model,
                "input": normalized_input,
                "instructions": instructions,
                "tools": normalized_tools,
                "tool_choice": tool_choice,
                **normalized_options,
            },
            indent=4,
            ensure_ascii=False,
        ),
    )

    with open("/app/config/config.json") as f:
        _config = json.load(f)

    api_key = _config.get("openai", {}).get("api_key")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OpenAI API key in config.json")

    payload = {
        "model": model,
        "input": normalized_input,
        **normalized_options,
    }
    if instructions:
        payload["instructions"] = instructions
    if normalized_tools:
        payload["tools"] = normalized_tools
    if tool_choice:
        payload["tool_choice"] = tool_choice

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=_config["timeout"]) as client:
        try:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as http_err:
            logger.error(
                "HTTP error from OpenAI Responses API: %s - %s",
                http_err.response.status_code,
                http_err.response.text,
            )
            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from OpenAI: {http_err.response.text}",
            )
        except httpx.RequestError as req_err:
            logger.error(f"Request error connecting to OpenAI Responses API: {req_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}",
            )
        except Exception as err:
            logger.error(f"Unexpected error calling OpenAI Responses API: {err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {err}",
            )

    json_response = response.json()
    logger.debug(f"🤖 Response from OpenAI Responses API:\n{json.dumps(json_response, indent=4, ensure_ascii=False)}")
    return OpenAIResponse.from_responses_api(json_response)
