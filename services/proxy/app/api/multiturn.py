"""
This module provides functionality for handling multi-turn conversational prompts and API requests 
for language models. It includes utilities for constructing formatted prompts based on conversation 
history and system-level instructions, as well as an API endpoint for processing multi-turn requests.

Modules and Functions:
- `build_multiturn_prompt`: Constructs a multi-turn conversational prompt using the provided 
    conversation history and system prompt.
- `from_api_multiturn`: FastAPI route handler for processing multi-turn API requests, validating 
    model compatibility, generating prompts, and interacting with the Ollama API.

Dependencies:
- `app.config`: Configuration settings for the application.
- `app.util`: Utility functions, including model compatibility checks.
- `app.prompts.dispatcher`: Retrieves the prompt builder function.
- `shared.models.proxy`: Data models for handling proxy requests and responses.
- `shared.log_config`: Logging configuration for structured logging.
- `httpx`: Asynchronous HTTP client for API requests.
- `fastapi`: Framework for building API routes.
- `dateutil.tz`: Timezone utilities for timestamp formatting.

Key Features:
- Supports instruct-style formatting for multi-turn conversation prompts.
- Includes error handling for model compatibility and API request failures.
- Logs detailed debug information for request and response processing.
"""

import app.config

from app.util import is_instruct_model
from app.prompts.dispatcher import get_prompt_builder

from shared.models.proxy import ProxyRequest, IncomingMessage, ProxyMultiTurnRequest, ProxyResponse


from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

import httpx
import json

from datetime import datetime
from dateutil import tz


local_tz = tz.tzlocal()
ts_with_offset = datetime.now(local_tz).isoformat(timespec="seconds")


from fastapi import APIRouter, HTTPException, status
router = APIRouter()


def build_multiturn_prompt(request: ProxyMultiTurnRequest, system_prompt: str) -> str:
    """
    Constructs a multi-turn conversational prompt based on the provided request and system prompt.

    Args:
        request (ProxyMultiTurnRequest): The request object containing a list of messages 
            representing the conversation history. Each message has a `role` (e.g., "system", 
            "user", "assistant") and `content` (the message text).
        system_prompt (str): The system-level prompt to include at the beginning of the conversation.

    Returns:
        str: A formatted string representing the multi-turn conversational prompt, 
        including the system prompt and the last 15 messages from the conversation history.

    Notes:
        - The system prompt is added as a header at the beginning of the prompt.
        - Only the last 15 messages (or fewer) from the conversation history are included.
        - Messages are formatted based on their role:
            - "system" messages are wrapped with "[INST] <<SYS>>...<<SYS>> [/INST]".
            - "user" messages are wrapped with "[INST] ... [/INST]".
            - If a "user" message is immediately followed by an "assistant" message, 
              they are concatenated in the same line.
        - Any unexpected message roles are skipped, and a warning is logged.
    """
    # 1) System prompt header
    prompt = f"[INST] <<SYS>>{system_prompt}<<SYS>> [/INST]\n\n"

    # 2) Only keep the last 30 (or fewer) messages
    messages = request.messages[-15:]
    num_messages = len(messages)
    i = 0

    # 3) Your original walk‑through logic
    while i < num_messages:
        msg = messages[i]

        if msg.role == "system":
            prompt += f"[INST] <<SYS>>{msg.content}<<SYS>> [/INST]\n"
            i += 1

        elif msg.role == "user":
            prompt += f"[INST] {msg.content} [/INST]"
            # look ahead for assistant reply
            if (i + 1 < num_messages) and (messages[i + 1].role == "assistant"):
                prompt += f" {messages[i + 1].content}\n"
                i += 2
            else:
                prompt += "\n"
                i += 1

        else:
            # skip any stray assistant/system messages
            logger.warning(f"Unexpected message at {i}: {msg.role}")
            i += 1

    return prompt


@router.post("/from/api/multiturn", response_model=ProxyResponse)
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

    logger.debug(f"/from/api/multiturn Request:\n{request.model_dump_json(indent=4)}")

    # fetch the builder function
    build_sys = await get_prompt_builder()

    # assemble a minimal ProxyRequest just to generate the system prompt
    # it only needs .message, .user_id, .context, .mode, .memories
    proxy_req = ProxyRequest(
        message=IncomingMessage(
            platform="api", 
            sender_id="internal", 
            text=request.messages[-1].content,
            timestamp=ts_with_offset,
            metadata={}
        ),
        user_id="randi",
        context="\n".join(f"{m.role}: {m.content}" for m in request.messages),
        memories=request.memories
    )

    # Check if the model supports instruct formatting.
    if not await is_instruct_model(request.model):
        logger.error(f"Model '{request.model}' is not instruct compatible.")

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{request.model}' is not instruct compatible."
        )

    # 3) now get your dynamic system prompt
    system_prompt = build_sys(proxy_req)

    # 4) build the full instruct‑style prompt
    full_prompt = build_multiturn_prompt(request, system_prompt)

    # Construct the payload for the Ollama API call
    payload = {
        "model": request.model,
        "prompt": full_prompt,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "stream": False,
        "raw": True
    }

    logger.debug(f"Request to Ollama API:\n{json.dumps(payload, indent=4, ensure_ascii=False)}")

    # Send the POST request using an async HTTP client
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(f"{app.config.OLLAMA_URL}/api/generate", json=payload)
            response.raise_for_status()

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from Ollama API: {http_err.response.status_code} - {http_err.response.text}")
            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from language model service: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error connecting to Ollama API: {req_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )

    json_response = response.json()
    logger.debug(f"Response from Ollama API:\n{json.dumps(json_response, indent=4, ensure_ascii=False)}")

    # Construct the ProxyResponse from the API response data.
    proxy_response = ProxyResponse(
        response=json_response.get("response"),
        generated_tokens=json_response.get("eval_count"),
        timestamp=datetime.now().isoformat()
    )

    logger.debug(f"/from/api/multiturn Response:\n{proxy_response.model_dump_json(indent=4)}")
    return proxy_response
