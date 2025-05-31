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

from shared.models.proxy import ProxyDiscordDMRequest, ProxyResponse, ChatMessages, OllamaResponse, OllamaRequest
from shared.models.prompt import BuildSystemPrompt

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

from app.util import build_multiturn_prompt
from app.prompts.dispatcher import get_system_prompt

from app.queue.router import queue
from shared.models.queue import ProxyTask

import uuid
import asyncio
from datetime import datetime
import json

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

with open('/app/shared/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]
LLM_DEFAULTS = _config["llm"]["mode"]["discord"]

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

    # now get your dynamic system prompt
    system_prompt = get_system_prompt(
        BuildSystemPrompt(
            memories=request.memories,
            mode=request.mode or 'work',
            platform='discord',
            summaries=request.summaries,
            username=request.message.display_name,
            timestamp=datetime.now().isoformat(timespec="seconds")
        )
    )

    # build the full instruct‑style prompt
    full_prompt = build_multiturn_prompt(ChatMessages(messages=request.messages), system_prompt)

    # Construct the payload for the Ollama API call
    payload = OllamaRequest(
        model=LLM_DEFAULTS['model'],
        prompt=full_prompt,
        temperature=LLM_DEFAULTS['options']['temperature'],
        max_tokens=LLM_DEFAULTS['options']['max_tokens'],
        stream=LLM_DEFAULTS['options']['stream'],
        raw=True
    )

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
    await queue.enqueue(task)

    try:
        result: OllamaResponse = await asyncio.wait_for(future, timeout=TIMEOUT)

    except asyncio.TimeoutError:
        queue.remove_task(task_id)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Task timed out"
        )

    # result is an OllamaResponse
    proxy_response = ProxyResponse(
        response=result.response,
        eval_count=result.eval_count,
        prompt_eval_count=result.prompt_eval_count,
        timestamp=datetime.now().isoformat()
    )

    queue.remove_task(task_id)

    return proxy_response
