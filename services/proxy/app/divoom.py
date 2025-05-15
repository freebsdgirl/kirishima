"""

"""

from shared.config import TIMEOUT
from shared.models.proxy import ProxyResponse, OllamaResponse, OllamaRequest, DivoomRequest

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

from app.queue.router import queue
from shared.models.queue import ProxyTask

import uuid
import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/divoom")
async def respond_with_divoom(request: DivoomRequest) -> ProxyResponse:
    logger.debug(f"/divoom Request: {request}")

    prompt = """[INST]<<SYS>>### TASK
Respond to the conversation as the Assistant. Output a single emoji in response to the conversation.
Emojis should be used to convey the sentiment or tone of the conversation from the Assistant's perspective.
Prefer facial expression emojis (e.g. 😊, 😏, 😐, 😬, 😢, 😎) unless the tone is better captured with a symbol.



### MESSAGE
"""
    lines = []
    for msg in request.messages:
        if msg.role == "user":
            lines.append(f"User: {msg.content}")
        elif msg.role == "assistant":
            lines.append(f"Assistant: {msg.content}")

    conversation_str = "\n".join(lines[-4:])

    logger.debug(f"Conversation string for intents: {conversation_str}")

    prompt += conversation_str
    prompt +="""

### OUTPUT
Respond to the conversation as the Assistant. Output a single emoji in response to the conversation.
<<SYS>>[/INST]"""

    # Construct the payload for the Ollama API call
    payload = OllamaRequest(
        model=request.model,
        prompt=prompt,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
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
