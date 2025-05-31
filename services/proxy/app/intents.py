"""
This module defines the FastAPI router and endpoint for intent detection in user conversations.

The `/intents` POST endpoint receives a request containing a conversation history and determines the intent of the user's latest message. It constructs a prompt for an LLM (Ollama) to classify the intent based on predefined categories (mode, memory, anime, email, or conversation) and extract relevant metadata. The endpoint enqueues the request as a blocking task, waits for the LLM's response, and returns a structured ProxyResponse.

Key functionalities:
- Builds a prompt with instructions and examples for intent classification.
- Supports multiple intent types with associated metadata extraction.
- Handles asynchronous task queuing and timeout management.
- Returns a standardized response with the detected intent and metadata.

Dependencies:
- FastAPI for API routing and exception handling.
- Shared models and configuration for request/response schemas and settings.
- Asynchronous task queue for managing LLM requests.
"""

from shared.models.proxy import ProxyResponse, OllamaResponse, OllamaRequest

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


@router.post("/intents")
async def respond_with_intents(request) -> ProxyResponse:
    logger.debug(f"/intents Request: {request}")

    prompt = """[INST]<<SYS>>### TASK
Determine the intent of the user's latest message.
Only consider the latest message in the conversation - other messages are for context only.
Choose from the list of intents. If nothing applies, respond with "Conversation".
Include metadata about the intent in the response.
If the intent is "conversation", include a "summary" in the metadata.
This summary should be a short, one-sentence summary that will be used to lookup memories.
Include a response in the metadata if the intent is not "conversation".



### INTENTS

- mode: the user is asking about the current mode of the system.
    metadata: 
        set: (string) The mode the user is asking to set.
- memory: The user is asking about the current memory of the system.
    metadata:
        create: (string) The user is asking to create a new memory.
        priority: (float) The priority of the created memory.
        delete: (string) The user is asking to delete a memory.
        search: (string) The user is asking to search for a memory.
- anime: The user is asking about anime.
    metadata:
        title: (string) The title of the anime.
        character: (string) The character from the anime.
        genre: (string) The genre of the anime.
- email: The user is asking about email.
    metadata:
        check_inbox: (boolean) The user is asking to check their inbox.
        send_email: (boolean) The user is asking to send an email.
        email: (string) the content of the email the user is asking to send.
        to: (string) The recipient of the email.
        subject: (string) The subject of the email.



### EXAMPLE

User: Set the mode to 'nsfw'.

Response:
{
    "intent": "mode",
    "metadata": {
        "set": true,
        "mode": "nsfw",
        "response": "Setting the mode to 'nsfw'."
    }
}



### EXAMPLE

User: Can you email my boss and tell him I need to take a day off? His email is john@doe.com

Response:
{
    "intent": "email",
    "metadata": {
        "send_email": true,
        "to": "john@doe.com",
        "email": "Hey! Something has come up and I need to take a day off. Thanks for your understanding.",
        "subject": "Day off request",
        "response": "Got it! I will send an email to your boss."
    }
}



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

### TASK
Determine the intent of the user's latest message.
Only consider the latest message in the conversation - other messages are for context only.
Choose from the list of intents. If nothing applies, respond with "Conversation".
Include metadata about the intent in the response.
If the intent is "conversation", include a "summary" in the metadata.
This summary should be a short, one-sentence summary that will be used to lookup memories.
Include a response in the metadata if the intent is not "conversation".<<SYS>>[/INST]"""

    # Construct the payload for the Ollama API call
    payload = OllamaRequest(
        model=request.model,
        prompt=prompt,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        stream=False,
        raw=True,
        format="json"
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
