"""
This module defines the FastAPI router and endpoint for handling single-turn completion requests
to the Ollama language model service. It receives a ProxyOneShotRequest, constructs an OllamaRequest
payload, enqueues the request as a blocking ProxyTask, and returns the generated response as a ProxyResponse.
Includes error handling for timeouts and logs incoming requests for debugging purposes.
"""

from shared.models.proxy import ProxyOneShotRequest, ProxyResponse, OllamaRequest

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")


from app.util import resolve_model_provider_options
from app.queue.router import queue, ollama_queue, openai_queue
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


@router.post("/api/singleturn", response_model=ProxyResponse)
async def from_api_completions(message: ProxyOneShotRequest) -> ProxyResponse:
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
    logger.debug(f"/api/singleturn Request:\n{message.model_dump_json(indent=4)}")

    # Resolve provider/model/options from model name
    #provider, model, options = resolve_model_provider_options(message.model)
    #logger.debug(f"Resolved provider/model/options: {provider}, {model}, {options}")

    if message.model == "nemo:latest":
        message.provider = "ollama"

    # Branch on provider and construct provider-specific request
    if message.provider == "ollama":
        payload = OllamaRequest(
            model=message.model,
            prompt=f"[INST]<<SYS>>{message.prompt}<<SYS>>[/INST]",
            options={
                "temperature": message.temperature,
                "max_tokens": message.max_tokens,
                "stream": False
            },
            stream=False,
            raw=True
        )
        queue_to_use = ollama_queue
    elif message.provider == "openai":
        from shared.models.proxy import OpenAIRequest  # Local import to avoid circular
        payload = OpenAIRequest(
            model=message.model,
            messages=[{"role": "user", "content": message.prompt}],
            options={
                "temperature": message.temperature,
                "max_tokens": message.max_tokens,
                "stream": False
            }
        )
        queue_to_use = openai_queue
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