import httpx

from shared.models.summary import CombinedSummaryRequest, Summary, SummaryMetadata
from shared.models.ledger import SummaryRequest
from shared.models.proxy import OllamaRequest, OllamaResponse

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

from shared.config import TIMEOUT

from app.queue.router import queue
from shared.models.queue import ProxyTask
import uuid
import asyncio

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/summary/user", status_code=status.HTTP_201_CREATED)
async def summary_user(request: SummaryRequest):
    """
    Summarize the user's messages.
    """
    logger.debug(f"Received summary request: {request}")

    user_label = request.user_alias or "Randi"
    assistant_label = "Kirishima"

    lines = []
    for msg in request.messages:
        if msg.role == "user":
            lines.append(f"{user_label}: {msg.content}")
        elif msg.role == "assistant":
            lines.append(f"{assistant_label}: {msg.content}")
    conversation_str = "\n".join(lines)

    logger.debug(f"Conversation string for summary: {conversation_str}")

    prompt = f"""[INST]<<SYS>>### Task: Summarize the following conversation between two people in a clear and concise manner.



### Conversation

{conversation_str}



### Instructions

- The summary should capture the main points and tone of the conversation.
- The summary should be no more than 64 tokens in length.
- The summary should be a single paragraph.

<</SYS>>[/INST]"""

    payload = OllamaRequest(
        prompt=prompt
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
    
    return {"summary": result.response}


@router.post("/summary/user/combined", status_code=status.HTTP_201_CREATED)
async def summary_user_combined(request: CombinedSummaryRequest):
    logger.debug(f"Received combined summary request: {request}")

    prompt = f"""[INST]<<SYS>>### Task: Using the given list of exising summaries, combine them into a single summary in a clear and concise manner.

### Summaries
"""
    
    for summary in request.summaries:
        prompt += f"[{summary.metadata.summary_type.value}] {summary.content}\n"

    prompt += """

### Instructions
- Focus on the key facts, decisions, or shifts in topic and tone that occurred.
- If the conversation involved high emotion (e.g., distress, anger), and the topic moved on, reflect that shift with neutral phrasing.
- The summary should be a single paragraph of no more than {request.max_tokens} tokens.<</SYS>>[/INST] """

    payload = OllamaRequest(
        prompt=prompt
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
    
    return {"summary": result.response}