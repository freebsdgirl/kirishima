from shared.models.proxy import AnthropicRequest, AnthropicResponse

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

import httpx
import json

from fastapi import HTTPException, status


async def send_to_anthropic(request: AnthropicRequest) -> AnthropicResponse:
    """
    Send a payload to the Anthropic API for generation using their OpenAI-compatible endpoint.
    """
    logger.debug(f"🎭 Request to Anthropic API:\n{json.dumps(request.model_dump(), indent=4, ensure_ascii=False)}")

    with open('/app/config/config.json') as f:
        _config = json.load(f)

    TIMEOUT = _config["timeout"]

    # Normalize tool_calls to always be a list (OpenAI-compatible format expects an array)
    def _normalize_tool_calls(messages):
        for msg in messages:
            if "tool_calls" in msg and msg["tool_calls"] is not None and not isinstance(msg["tool_calls"], list):
                msg["tool_calls"] = [msg["tool_calls"]]
        return messages

    payload = {
        "model": request.model,
        "messages": _normalize_tool_calls(request.messages),
        **(request.options or {})
    }
    if getattr(request, "tools", None):
        payload["tools"] = request.tools

        if getattr(request, "tool_choice", None):
            payload["tool_choice"] = request.tool_choice

    # Get Anthropic API key from config.json
    api_key = _config.get("anthropic", {}).get("api_key")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing Anthropic API key in config.json")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.post(
                "https://api.anthropic.com/v1/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from Anthropic API: {http_err.response.status_code} - {http_err.response.text}")
            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from Anthropic: {http_err.response.text}"
            )
        except httpx.RequestError as req_err:
            logger.error(f"Request error connecting to Anthropic API: {req_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {e}"
            )

    json_response = response.json()
    logger.debug(f"🎭 Response from Anthropic API:\n{json.dumps(json_response, indent=4, ensure_ascii=False)}")

    # Parse OpenAI-compatible response format
    anthropic_response = AnthropicResponse.from_api(json_response)
    return anthropic_response
