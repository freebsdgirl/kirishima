import httpx

from shared.models.summary import CombinedSummaryRequest, SummaryRequest
from shared.models.proxy import OllamaRequest, OllamaResponse

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

from app.queue.router import queue
from shared.models.queue import ProxyTask
import uuid
import asyncio
import json

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

with open('/app/shared/config.json') as f:
    _config = json.load(f)
TIMEOUT = _config["timeout"]


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


from datetime import datetime

def format_timestamp(ts: str) -> str:
    dt = datetime.fromisoformat(ts.replace("Z", ""))  # handle 'Z' if it's present
    return dt.strftime("%A, %B %d")


@router.post("/summary/user/combined", status_code=status.HTTP_201_CREATED)
async def summary_user_combined(request: CombinedSummaryRequest):
    logger.debug(f"Received combined summary request: {request}")

    prompt = f"""[INST]<<SYS>>### Task: Using the provided daily summaries, generate a weekly summary that reflects how events unfolded over time.

### Daily Summaries
"""
    for summary in request.summaries:
        date_str = format_timestamp(summary.metadata.timestamp_begin)
        prompt += f"[{summary.metadata.summary_type.upper()} – {date_str}] {summary.content}\n"

    prompt += f"""

### Instructions
- Organize the summary chronologically. Use time indicators like “On Monday…”, "The third week…", “Later that week…”, “By Friday the 22nd…” when appropriate.
- Emphasize key actions, decisions, emotional shifts, and recurring themes.
- Maintain a coherent narrative flow, but don’t compress multiple days into a single moment.
- The tone should be reflective and concise, not clinical or overly detailed.
- Output a single paragraph not exceeding {request.max_tokens} tokens.
<</SYS>>[/INST] """

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