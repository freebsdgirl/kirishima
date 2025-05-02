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

from shared.config import TIMEOUT, LLM_DEFAULTS
from shared.models.proxy import ProxyResponse, ChatMessages, OllamaResponse, OllamaRequest
from shared.models.prompt import BuildSystemPrompt
from shared.models.imessage import ProxyiMessageRequest, iMessage

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

from app.util import build_multiturn_prompt
from app.prompts.dispatcher import get_system_prompt

from app.queue.router import queue
from shared.models.queue import ProxyTask

import uuid
import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/imessage")
async def imessage(request: ProxyiMessageRequest) -> ProxyResponse:
    logger.debug(f"/imessage Request: {request}")

    # now get your dynamic system prompt
    system_prompt = get_system_prompt(
        BuildSystemPrompt(
            memories=request.memories,
            mode=request.mode or 'work',
            platform=request.platform or 'imessage',
            summaries=request.summaries,
            username=request.contact.aliases[0] if request.contact.aliases else None,
            timestamp=datetime.now().isoformat(timespec="seconds")
        )
    )

    # build the full instruct‑style prompt
    full_prompt = build_multiturn_prompt(ChatMessages(messages=request.messages), system_prompt)

    # Construct the payload for the Ollama API call
    payload = OllamaRequest(
        model=LLM_DEFAULTS['model'],
        prompt=full_prompt,
        temperature=LLM_DEFAULTS['temperature'],
        max_tokens=LLM_DEFAULTS['max_tokens'],
        stream=False,
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
