"""
This module defines the FastAPI router and endpoint for handling single-turn completion requests
to the Ollama language model service. It receives a ProxyOneShotRequest, constructs an OllamaRequest
payload, enqueues the request as a blocking ProxyTask, and returns the generated response as a ProxyResponse.
Includes error handling for timeouts and logs incoming requests for debugging purposes.
"""

from shared.config import TIMEOUT

from shared.models.proxy import ProxyOneShotRequest, ProxyResponse, OllamaRequest, OllamaResponse

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")


from app.queue.router import queue
from shared.models.queue import ProxyTask
import uuid
import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

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

    # Construct the payload for the Ollama API request
    payload = OllamaRequest(
        model=message.model,
        prompt=message.prompt,
        temperature=message.temperature,
        max_tokens=message.max_tokens,
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