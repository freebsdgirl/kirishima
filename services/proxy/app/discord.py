"""
This module provides an API endpoint for handling Discord direct message (DM) proxy requests.

It defines a FastAPI router with a single POST endpoint `/discord/dm` that processes incoming Discord DM requests by:
1. Constructing a minimal ProxyRequest from the incoming Discord message.
2. Generating a dynamic system prompt based on the request context.
3. Building a multi-turn prompt for the language model.
4. Enqueuing the request as a blocking task in the task queue.
5. Awaiting and returning the response from the Ollama API.

Modules and Classes:
- Imports shared configuration, models, and logging utilities.
- Utilizes utility functions for prompt construction and system prompt dispatching.
- Integrates with a task queue for asynchronous processing.

- HTTPException with status 504 if the task times out.

- OllamaResponse: The generated response from the language model.
"""

from shared.models.proxy import ProxyDiscordDMRequest, ProxyResponse, OllamaRequest
from shared.models.prompt import BuildSystemPrompt

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

from app.util import build_multiturn_prompt, resolve_model_provider_options
from app.prompts.dispatcher import get_system_prompt

from app.queue.router import ollama_queue, openai_queue
from shared.models.queue import ProxyTask

import uuid
import asyncio
from datetime import datetime
import json

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]

@router.post("/discord/dm")
async def discord_dm(request: ProxyDiscordDMRequest) -> ProxyResponse:
    """
    Handle Discord direct message (DM) proxy requests.

    This endpoint processes incoming Discord DM requests by:
    1. Constructing a proxy request from the Discord message
    2. Generating a dynamic system prompt
    3. Building a multi-turn prompt
    4. Enqueueing the request to the task queue
    5. Waiting for and returning the Ollama API response

    Args:
        request (ProxyDiscordDMRequest): The incoming Discord DM request details

    Returns:
        ProxyResponse: The generated response from the language model

    Raises:
        HTTPException: If the task times out after the specified timeout period
    """
    logger.debug(f"/discord/dm Request: {request}")

    # resolve provider/model/options from mode
    provider, model, options = resolve_model_provider_options(request.model if hasattr(request, 'model') and request.model else 'discord')
    logger.debug(f"Resolved provider/model/options: {provider}, {model}, {options}")

    # now get your dynamic system prompt
    system_prompt = get_system_prompt(
        BuildSystemPrompt(
            memories=request.memories,
            mode=request.mode or 'discord',
            platform='discord',
            summaries=request.summaries,
            username=request.message.display_name,
            timestamp=datetime.now().isoformat(timespec="seconds")
        ),
        provider=provider,
        mode=request.mode or 'discord'
    )

    # build the full instruct‑style prompt
    full_prompt = build_multiturn_prompt(request.messages, system_prompt)

    # Branch on provider and construct provider-specific request
    if provider == "ollama":
        payload = OllamaRequest(
            model=model,
            prompt=full_prompt,
            temperature=options.get('temperature'),
            max_tokens=options.get('max_tokens'),
            stream=options.get('stream', False),
            raw=True
        )
        queue_to_use = ollama_queue
    elif provider == "openai":
        from shared.models.proxy import OpenAIRequest  # Local import to avoid circular
        payload = OpenAIRequest(
            model=model,
            messages=request.messages,
            options=options
        )
        queue_to_use = openai_queue
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    # Create a blocking ProxyTask
    task_id = str(uuid.uuid4())
    future = asyncio.Future()
    task = ProxyTask(
        priority=2,
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
