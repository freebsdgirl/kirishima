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
from shared.config import TIMEOUT
from shared.models.proxy import AlignmentRequest, ChatMessages, ProxyMultiTurnRequest, ProxyResponse, OllamaRequest, OllamaResponse
from shared.models.prompt import BuildSystemPrompt

from app.util import build_multiturn_prompt
from app.prompts.dispatcher import get_system_prompt

from app.config import ALIGNMENT

from app.queue.router import queue
from shared.models.queue import ProxyTask
import uuid
import asyncio

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

import json

from datetime import datetime
from dateutil import tz

local_tz = tz.tzlocal()
ts_with_offset = datetime.now(local_tz).isoformat(timespec="seconds")

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/api/multiturn", response_model=ProxyResponse)
async def from_api_multiturn(request: ProxyMultiTurnRequest) -> ProxyResponse:
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

    # now get your dynamic system prompt
    system_prompt = get_system_prompt(
        BuildSystemPrompt(
            memories=request.memories,
            mode=request.mode or 'work',
            platform=request.platform or 'api',
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
        priority=1,
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

    if ALIGNMENT:
        alignment_payload = AlignmentRequest(
            user=request.messages[-1].content,
            response=proxy_response
        )

        alignment_prompt = get_system_prompt(alignment_payload)

        # Construct the payload for the Ollama API call
        payload = OllamaRequest(
            model=request.model,
            prompt=alignment_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False,
            raw=True
        )

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