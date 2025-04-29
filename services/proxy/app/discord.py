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

from shared.config import TIMEOUT
from shared.models.proxy import ProxyDiscordDMRequest, ProxyResponse, ProxyRequest, IncomingMessage, ChatMessages, OllamaResponse, OllamaRequest

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

from app.util import build_multiturn_prompt
from app.prompts.dispatcher import get_system_prompt


from app.queue.router import queue
from shared.models.queue import ProxyTask
import uuid
import asyncio

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/discord/dm")
async def discord_dm(request: ProxyDiscordDMRequest) -> OllamaResponse:
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

    # assemble a minimal ProxyRequest just to generate the system prompt
    # it only needs .message, .user_id, .context, .mode, .memories
    proxy_req = ProxyRequest(
        message=IncomingMessage(
            platform="discord", 
            sender_id=request.contact.id,
            text=request.message.content,
            timestamp=request.message.timestamp,
            metadata={
                "name": request.message.display_name
            }
        ),
        user_id=request.contact.id,
        context=request.message.display_name,
        mode=request.mode,
        memories=request.memories,
        summaries=request.summaries
    )

    # now get your dynamic system prompt
    system_prompt = get_system_prompt(proxy_req)

    # 4) build the full instruct‑style prompt
    full_prompt = build_multiturn_prompt(ChatMessages(messages=request.messages), system_prompt)

    # Construct the payload for the Ollama API call
    payload = OllamaRequest(
        prompt=full_prompt
    )

    # Create a blocking ProxyTask
    task_id = str(uuid.uuid4())
    future = asyncio.Future()
    task = ProxyTask(
        priority=5,
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
