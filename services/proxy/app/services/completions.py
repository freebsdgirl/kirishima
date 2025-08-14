"""
Refactored single-turn completions: accepts SingleTurnRequest (mode-based) only.
"""
from shared.models.proxy import SingleTurnRequest, ProxyResponse, OllamaRequest, OpenAIRequest, AnthropicRequest

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

from app.services.util import _resolve_model_provider_options

import json
from datetime import datetime

from fastapi import HTTPException

from app.services.send_to_ollama import send_to_ollama
from app.services.send_to_openai import send_to_openai
from app.services.send_to_anthropic import send_to_anthropic


async def _completions(message: SingleTurnRequest) -> ProxyResponse:
    with open('/app/config/config.json') as f:
        _config = json.load(f)

    logger.debug(f"/api/singleturn Request (mode-based):\n{message.model_dump_json(indent=4)}")

    provider, actual_model, options = _resolve_model_provider_options(message.model)

    if provider == "ollama":
        payload = OllamaRequest(
            model=actual_model,
            prompt=f"[INST]<<SYS>>{message.prompt}<<SYS>>[/INST]",
            options=options,
            stream=False,
            raw=True
        )
    elif provider == "openai":
        payload = OpenAIRequest(
            model=actual_model,
            messages=[{"role": "user", "content": message.prompt}],
            options=options
        )
    elif provider == "anthropic":
        payload = AnthropicRequest(
            model=actual_model,
            messages=[{"role": "user", "content": message.prompt}],
            options=options
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    async def _dispatch(p):
        if isinstance(p, OllamaRequest):
            return await send_to_ollama(p)
        if isinstance(p, OpenAIRequest):
            return await send_to_openai(p)
        if isinstance(p, AnthropicRequest):
            return await send_to_anthropic(p)
        raise HTTPException(status_code=500, detail="Unsupported payload type for dispatch")

    logger.debug(f"Dispatching directly to provider={provider} model={actual_model} (no queue)")
    try:
        result = await _dispatch(payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during provider dispatch: {e}")
        raise HTTPException(status_code=500, detail=f"Provider dispatch failed: {e}")

    proxy_response = ProxyResponse(
        response=getattr(result, 'response', None),
        eval_count=getattr(result, 'eval_count', None),
        prompt_eval_count=getattr(result, 'prompt_eval_count', None),
        tool_calls=getattr(result, 'tool_calls', None),
        function_call=getattr(result, 'function_call', None),
        timestamp=datetime.now().isoformat()
    )

    return proxy_response