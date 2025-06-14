"""
This module defines an API endpoint for handling multi-turn conversation requests.
The `/api/multiturn` endpoint processes requests to generate responses for multi-turn
conversations using a language model. It validates the request, constructs a system
prompt, builds an instruct-style prompt, and communicates with the Ollama API to
generate a response. The endpoint returns the generated response along with metadata.
Modules:
    - shared.config: Provides configuration constants such as TIMEOUT.
    - shared.models.proxy: Defines data models for ProxyRequest, ChatMessages, etc.
    - app.util: Contains utility functions for building prompts.
    - app.config: Application-specific configuration.
    - shared.log_config: Provides logging configuration.
    - httpx: Used for making asynchronous HTTP requests.
    - json: Used for JSON serialization and deserialization.
    - datetime, dateutil.tz: Used for handling timestamps with timezone information.
    - fastapi: Provides the APIRouter and HTTPException classes for API routing and error handling.
Functions:
    - from_api_multiturn(request: ProxyMultiTurnRequest) -> ProxyResponse:
        Handles multi-turn API requests by generating prompts for language models.
"""
from shared.models.proxy import MultiTurnRequest, ProxyResponse, OllamaRequest
from shared.models.prompt import BuildSystemPrompt

from app.util import build_multiturn_prompt, resolve_model_provider_options
from app.prompts.dispatcher import get_system_prompt

from app.queue.router import ollama_queue, openai_queue
from shared.models.queue import ProxyTask
import uuid
import asyncio

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

import json
import os

from datetime import datetime
from dateutil import tz

local_tz = tz.tzlocal()
ts_with_offset = datetime.now(local_tz).isoformat(timespec="seconds")

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

with open('/app/shared/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


@router.post("/api/multiturn", response_model=ProxyResponse)
async def from_api_multiturn(request: MultiTurnRequest) -> ProxyResponse:
    """ 
    Handle multi-turn API requests by generating prompts for language models.

    Processes a multi-turn conversation request, validates model compatibility,
    builds an instruct-style prompt, and sends a request to the Ollama API.
    Returns a ProxyResponse with the generated text and metadata.

    Args:
        request (ProxyMultiTurnRequest): Multi-turn conversation request details.

    Returns:
        ProxyResponse: Generated response from the language model.

    Raises:
        HTTPException: If the model is not instruct-compatible or API request fails.
    """

    logger.debug(f"/api/multiturn Request:\n{json.dumps(request.model_dump(), indent=4, ensure_ascii=False)}")

    # resolve provider/model/options from mode
    provider, model, options = resolve_model_provider_options(request.model)
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

    # build the full instruct‑style prompt
    full_prompt = build_multiturn_prompt(request.messages, system_prompt)

    # Branch on provider and construct provider-specific request/payload
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
        # Prepend system prompt as a system message for OpenAI
        openai_messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + request.messages
        payload = OpenAIRequest(
            model=model,
            messages=openai_messages,
            options=options,
            tools=request.tools,
            tool_choice="auto"  # Use auto tool choice for OpenAI
        )
        queue_to_use = openai_queue
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

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

    # Remove tool execution logic: proxy should not process tool calls

    queue_to_use.remove_task(task_id)

    return proxy_response