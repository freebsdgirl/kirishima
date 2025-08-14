from shared.models.proxy import MultiTurnRequest, ProxyResponse, OllamaRequest, OpenAIRequest, AnthropicRequest
from shared.models.prompt import BuildSystemPrompt

from app.services.util import _build_multiturn_prompt, _resolve_model_provider_options
from app.prompts.dispatcher import get_system_prompt

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

import json

from datetime import datetime
from dateutil import tz

local_tz = tz.tzlocal()
ts_with_offset = datetime.now(local_tz).isoformat(timespec="seconds")

from fastapi import HTTPException, status

from app.services.send_to_ollama import send_to_ollama
from app.services.send_to_openai import send_to_openai
from app.services.send_to_anthropic import send_to_anthropic

async def _chat_completions(request: MultiTurnRequest) -> ProxyResponse:
    """ 
    Handle multi-turn API requests by generating prompts for language models.

    Processes a multi-turn conversation request, validates model compatibility,
    builds an instruct-style prompt, and directly dispatches to the provider API (no queue).
    Returns a ProxyResponse with the generated text and metadata.

    Args:
        request (ProxyMultiTurnRequest): Multi-turn conversation request details.

    Returns:
        ProxyResponse: Generated response from the language model.

    Raises:
        HTTPException: If the model is not instruct-compatible or API request fails.
    """
    logger.debug(f"/api/multiturn Request:\n{json.dumps(request.model_dump(), indent=4, ensure_ascii=False)}")

    with open('/app/config/config.json') as f:
        _config = json.load(f)

    # resolve provider/model/options from mode (request.model is interpreted as a mode)
    provider, model, options = _resolve_model_provider_options(request.model)
    logger.debug(f"Resolved provider/model/options: {provider}, {model}, {options}")

    # now get your dynamic system prompt
    system_prompt = get_system_prompt(
        BuildSystemPrompt(
            memories=request.memories,
            mode=request.model or 'default',
            platform=request.platform or 'api',
            summaries=request.summaries,
            username=request.username or 'Randi',
            timestamp=datetime.now().isoformat(timespec="seconds"),
            agent_prompt=request.agent_prompt or None,
        ),
        provider=provider,
        mode=request.model or 'default'
    )

    # build the full instruct‑style prompt (used for non-OpenAI/Anthropic providers expecting single string)
    full_prompt = _build_multiturn_prompt(request.messages, system_prompt)

    # Construct provider-specific request/payload
    if provider == "ollama":
        payload = OllamaRequest(
            model=model,
            prompt=full_prompt,
            temperature=options.get('temperature'),
            max_tokens=options.get('max_tokens'),
            stream=options.get('stream', False),
            raw=True
        )
    elif provider == "openai":
        openai_messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + request.messages
        payload = OpenAIRequest(
            model=model,
            messages=openai_messages,
            options=options,
            tools=request.tools,
            tool_choice="auto"
        )
    elif provider == "anthropic":
        anthropic_messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + request.messages
        payload = AnthropicRequest(
            model=model,
            messages=anthropic_messages,
            options=options,
            tools=request.tools,
            tool_choice="auto"
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    # Direct dispatch helper
    async def _dispatch(p):
        if isinstance(p, OllamaRequest):
            return await send_to_ollama(p)
        if isinstance(p, OpenAIRequest):
            return await send_to_openai(p)
        if isinstance(p, AnthropicRequest):
            return await send_to_anthropic(p)
        raise HTTPException(status_code=500, detail="Unsupported payload type for dispatch")

    logger.debug(f"Dispatching directly to provider={provider} model={model} (no queue)")
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