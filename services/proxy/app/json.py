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

from shared.models.proxy import RespondJsonRequest, ProxyResponse, OllamaRequest

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

from app.queue.router import ollama_queue, openai_queue
from shared.models.queue import ProxyTask

from app.util import resolve_model_provider_options

import uuid
import asyncio
from datetime import datetime
import json

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

with open('/app/config/config.json') as f:
    _config = json.load(f)
TIMEOUT = _config["timeout"]


@router.post("/json")
async def respond_with_json(request: RespondJsonRequest) -> ProxyResponse:
    logger.debug(f"/json Request: {request}")

    # Resolve provider/model/options from model name
    provider, model, options = resolve_model_provider_options(request.model)
    logger.debug(f"Resolved provider/model/options: {provider}, {model}, {options}")

    # Branch on provider and construct provider-specific request
    if provider == "ollama":
        payload = OllamaRequest(
            model=model,
            prompt=request.prompt,
            temperature=options.get('temperature'),
            max_tokens=options.get('max_tokens'),
            stream=options.get('stream', False),
            raw=True,
            format=getattr(request, 'format', None)
        )
        queue_to_use = ollama_queue
    elif provider == "openai":
        from shared.models.proxy import OpenAIRequest  # Local import to avoid circular
        payload = OpenAIRequest(
            model=model,
            messages=[{"role": "user", "content": request.prompt}],
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
