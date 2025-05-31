"""
This module defines a FastAPI router for handling JSON-based proxy requests.

Endpoints:
    - POST /json: Accepts a `RespondJsonRequest` and returns a `ProxyResponse` after processing
      the request through a task queue and awaiting a response from the Ollama API.

Key Components:
    - Constructs an `OllamaRequest` payload from the incoming request.
    - Enqueues a blocking `ProxyTask` with a unique task ID and awaits its completion.
    - Handles timeout scenarios by removing the task from the queue and raising an HTTP 504 error.
    - Returns a `ProxyResponse` containing the result and relevant metadata.

Dependencies:
    - shared.config.TIMEOUT: Timeout duration for task completion.
    - shared.models.proxy: Data models for request and response handling.
    - shared.log_config: Logger configuration.
    - app.queue.router.queue: Task queue for proxy requests.
    - shared.models.queue.ProxyTask: Task model for queue operations.

"""

from shared.models.proxy import RespondJsonRequest, ProxyResponse, OllamaResponse, OllamaRequest

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

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


@router.post("/json")
async def respond_with_json(request: RespondJsonRequest) -> ProxyResponse:
    logger.debug(f"/json Request: {request}")

    # Construct the payload for the Ollama API call
    payload = OllamaRequest(
        model=request.model,
        prompt=request.prompt,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        stream=False,
        raw=True,
        format=request.format
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
