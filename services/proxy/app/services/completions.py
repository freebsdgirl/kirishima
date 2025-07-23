"""
This module provides the core logic for handling single-turn completion requests
to various language model providers (Ollama, OpenAI, Anthropic) via a unified API.

Functions:
    _completions(message: ProxyOneShotRequest) -> ProxyResponse:
        Handles a completion request by determining the appropriate provider,
        constructing the provider-specific payload, enqueuing the request for
        asynchronous processing, and returning a normalized ProxyResponse.

Configuration:
    Loads timeout and other settings from '/app/config/config.json'.

Dependencies:
    - shared.models.proxy: Data models for requests and responses.
    - shared.log_config: Logger configuration.
    - app.util: Utility for resolving model/provider/options.
    - app.queue.router: Provider-specific queues.
    - shared.models.queue: ProxyTask definition.
    - fastapi: For HTTPException and status codes.

    HTTPException: For unknown providers or timeout errors.
"""
from shared.models.proxy import ProxyOneShotRequest, ProxyResponse, OllamaRequest

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

from app.services.util import _resolve_model_provider_options
from app.services.queue import ollama_queue, openai_queue, anthropic_queue
from shared.models.queue import ProxyTask

import uuid
import asyncio
from datetime import datetime
import json

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


async def _completions(message: ProxyOneShotRequest) -> ProxyResponse:
    """
    Handle API completions request by forwarding the request to the Ollama language model service.

    This endpoint takes a ProxyOneShotRequest, constructs a payload for the Ollama API,
    sends an asynchronous request, and returns a ProxyResponse with the generated
    text and metadata.

    Args:
        message (ProxyOneShotRequest): The completion request containing model, prompt,
            temperature, and max tokens parameters.

    Returns:
        ProxyResponse: The response from the language model, including generated
            text, token count, and timestamp.

    Raises:
        HTTPException: If there are connection or communication errors with the Ollama service.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)

    TIMEOUT = _config["timeout"]

    logger.debug(f"/api/singleturn Request:\n{message.model_dump_json(indent=4)}")

    options = {
        "temperature": message.temperature,
        "max_tokens": message.max_tokens,
        "stream": False
    }

    model = message.model

    if not message.provider:
        if message.model.startswith("claude"):
            message.provider = "anthropic"
        elif message.model.startswith("gpt"):
            message.provider = "openai"
        else:
            message.provider = "ollama"

    # Branch on provider and construct provider-specific request
    if message.provider == "ollama":
        payload = OllamaRequest(
            model=model,
            prompt=f"[INST]<<SYS>>{message.prompt}<<SYS>>[/INST]",
            options=options,
            stream=False,
            raw=True
        )
        queue_to_use = ollama_queue
    elif message.provider == "openai":
        from shared.models.proxy import OpenAIRequest  # Local import to avoid circular
        payload = OpenAIRequest(
            model=model,
            messages=[{"role": "user", "content": message.prompt}],
            options=options
        )
        queue_to_use = openai_queue
    elif message.provider == "anthropic":
        from shared.models.proxy import AnthropicRequest  # Local import to avoid circular
        payload = AnthropicRequest(
            model=model,
            messages=[{"role": "user", "content": message.prompt}],
            options=options
        )
        queue_to_use = anthropic_queue
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {message.provider}")

    # Create a blocking ProxyTask
    task_id = str(uuid.uuid4())
    future = asyncio.Future()
    task = ProxyTask(
        priority=1,
        task_id=task_id,
        payload=payload,
        blocking=True,
        future=future,
        callback=None
    )
    await queue_to_use.enqueue(task)

    try:
        result = await asyncio.wait_for(future, timeout=TIMEOUT)
    except asyncio.TimeoutError:
        queue_to_use.remove_task(task_id)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Task timed out"
        )

    # result is a provider-specific response; normalize to ProxyResponse
    proxy_response = ProxyResponse(
        response=getattr(result, 'response', None),
        eval_count=getattr(result, 'eval_count', None),
        prompt_eval_count=getattr(result, 'prompt_eval_count', None),
        tool_calls=getattr(result, 'tool_calls', None),
        function_call=getattr(result, 'function_call', None),
        timestamp=datetime.now().isoformat()
    )

    queue_to_use.remove_task(task_id)

    return proxy_response