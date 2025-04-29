"""
This module defines the iMessage proxy endpoint for handling multi-turn chat requests via FastAPI.

It processes incoming iMessage requests, constructs system prompts and full instruct-style prompts,
and dispatches them to an LLM (Ollama) through a queue-based task system. The endpoint supports
timeout handling and returns structured responses.

Endpoints:
    - POST /from/imessage: Accepts a ProxyMultiTurnRequest, builds prompts, enqueues a task, and returns an OllamaResponse.

Dependencies:
    - shared.config.TIMEOUT: Timeout for LLM responses.
    - shared.models.proxy: Data models for proxy requests and responses.
    - shared.models.prompt: System prompt builder.
    - app.util.build_multiturn_prompt: Utility to build chat prompts.
    - app.prompts.dispatcher.get_system_prompt: Retrieves dynamic system prompts.
    - app.queue.router.queue: Task queue for LLM requests.
    - shared.models.queue.ProxyTask: Task model for queueing.
    - shared.log_config.get_logger: Logger configuration.
    - fastapi: Web framework for API routing.

Logging:
    - Logs incoming requests and errors.

Raises:
    - HTTPException 504 if the LLM task times out.
"""
from shared.config import TIMEOUT
from shared.models.proxy import ProxyMultiTurnRequest, ChatMessages, OllamaRequest, OllamaResponse
from shared.models.prompt import BuildSystemPrompt

from app.util import build_multiturn_prompt
from app.prompts.dispatcher import get_system_prompt

from app.queue.router import queue
from shared.models.queue import ProxyTask
import uuid
import asyncio

from datetime import datetime

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/from/imessage", response_model=OllamaResponse)
async def from_imessage(request: ProxyMultiTurnRequest) -> OllamaResponse:
    """
    Handle incoming iMessage requests by processing the message through a prompt builder and sending it to an LLM.

    Args:
        message (ProxyRequest): The incoming iMessage request containing mode and memories.

    Returns:
        dict: A response containing the status, LLM reply, and raw response data.
    """
    logger.debug(f"/from/imessage request: {request}")

    # now get your dynamic system prompt
    system_prompt = get_system_prompt(
        BuildSystemPrompt(
            memories=request.memories,
            mode=request.mode or 'work',
            platform=request.platform or 'imessage',
            summaries=request.summaries,
            username=request.username or 'Randi',
            timestamp=datetime.now().isoformat(timespec="seconds")
        )
    )

    # build the full instruct‑style prompt
    full_prompt = build_multiturn_prompt(ChatMessages(messages=request.messages), system_prompt)

    # Construct the payload for the Ollama API call
    payload = OllamaRequest(
        model=request.model,
        prompt=full_prompt,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        stream=False,
        raw=True
    )

    # Create a blocking ProxyTask
    task_id = str(uuid.uuid4())
    future = asyncio.Future()
    task = ProxyTask(
        priority=0,
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

    queue.remove_task(task_id)

    return result
