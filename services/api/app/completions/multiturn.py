"""
This module provides FastAPI endpoints for handling OpenAI-compatible chat completion requests,
including both multi-turn conversations and special single-turn task routing.

Endpoints:
    - POST /chat/completions: Redirects to /v1/chat/completions for backward compatibility.
    - POST /v1/chat/completions: Processes chat completion requests, supporting:
        1. Special task routing for messages starting with '### Task'
        2. Multi-turn conversation handling via internal brain service

Features:
    - Redirects legacy endpoints to versioned endpoints.
    - Detects and routes special single-turn tasks to the completions endpoint.
    - Forwards multi-turn chat requests to an internal brain service.
    - Handles error scenarios with appropriate HTTP responses.
    - Formats responses to be compatible with OpenAI's API schema.
    - Logs request and response details for debugging and traceability.

Dependencies:
    - FastAPI for API routing and response handling.
    - httpx for asynchronous HTTP requests to internal services.
    - Shared models for request and response validation.
    - Custom logging configuration for structured logging.
    - Configuration loaded from JSON for runtime parameters (e.g., timeout).

"""

from shared.models.proxy import MultiTurnRequest, ProxyResponse
from shared.models.api import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice, ChatUsage, CompletionRequest

from app.completions.singleturn import openai_v1_completions

from shared.log_config import get_logger
logger = get_logger(f"api.{__name__}")

import uuid
import httpx
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse
router = APIRouter()

import json

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]

@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def openai_completions(request: ChatCompletionRequest) -> RedirectResponse:

    """
    Redirects requests from the '/completions' endpoint to the '/v1/completions' endpoint.

    This function provides a temporary redirect for compatibility with different API endpoint versions,
    ensuring that requests to the base '/completions' route are seamlessly forwarded to the versioned endpoint.

    Args:
        request (OpenAICompletionRequest): The incoming completions request.

    Returns:
        RedirectResponse: A temporary redirect to the '/v1/completions' endpoint.
    """
    return RedirectResponse(
        url="/v1/chat/completions",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )


@router.post("/v1/chat/completions")
async def chat_completions(data: ChatCompletionRequest):
    """
    Handle OpenAI chat completions with support for special task routing and multi-turn conversations.

    This endpoint processes chat completion requests, supporting two primary modes:
    1. Special task routing for requests starting with '### Task'
    2. Multi-turn conversation handling for standard chat interactions

    Handles request filtering, proxy communication with internal brain service,
    token usage calculation, and OpenAI-compatible response generation.

    Args:
        request (ChatCompletionRequest): The incoming chat completion request.

    Returns:
        ChatCompletionResponse: A formatted chat completion response compatible with OpenAI's API.

    Raises:
        HTTPException: For various error scenarios including HTTP and request errors.
    """
    logger.debug(f"/v1/chat/completions Request")

    # Check if the first user message starts with "### Task"
    if data.messages and data.messages[0]["role"] == "user" and data.messages[0]["content"].startswith("### Task"):
        task_prompt = data.messages[0]["content"][len("### Task"):].lstrip()
        logger.debug("Detected special '### Task' prefix. Delegating request to the completions endpoint.")

        # Use new CompletionRequest (content, not prompt; no temperature/max_tokens)
        completion_request = CompletionRequest(
            model="gpt-4.1-nano",  # Hardcoded model for single-turn completions
            options={},
            content=task_prompt,
            n=1
        )
        response = await openai_v1_completions(completion_request, None)
        completion = response.model_dump()
        try:
            chat_response = ChatCompletionResponse(
                id=completion["id"],
                object="chat.completion",
                created=completion["created"],
                model=data.model,  # Use the original mode here
                choices=[
                    ChatCompletionChoice(
                        index=choice["index"],
                        message={"role": "assistant", "content": choice["text"]},
                        finish_reason=choice.get("finish_reason", "stop")
                    )
                    for choice in completion.get("choices", [])
                ],
                usage=ChatUsage(
                    prompt_tokens=completion["usage"]["prompt_tokens"],
                    completion_tokens=completion["usage"]["completion_tokens"],
                    total_tokens=completion["usage"]["total_tokens"]
                )
            )
        except Exception as e:
            logger.error(f"Error converting completions response to chat format: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error converting completions response to chat format: {e}"
            )
        return chat_response

    # Multi-turn: Use data.messages directly (assume already validated)
    # Pass mode as model, do not resolve to provider/model/options here
    multiturn_request = MultiTurnRequest(
        model=data.model,  # This is the mode string, e.g. "default", "nsfw", etc.
        messages=data.messages,
        platform="api"
    )
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            # get brain's port from environment
            brain_port = os.getenv("BRAIN_PORT", 4207)

            response = await client.post(
                f"http://brain:{brain_port}/api/multiturn",
                json=multiturn_request.model_dump()
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error forwarding to brain: {http_err.response.status_code} - {http_err.response.text}")
            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from multi-turn brain: {http_err.response.text}"
            )
        except httpx.RequestError as e:
            logger.error(f"Request error when forwarding to brain: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Connection error to brain: {e}"
            )
        except Exception as e:
            logger.exception(f"Error retrieving service address for brain: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error contacting brain: {e}"
            )
    try:
        proxy_response = ProxyResponse.model_validate(response.json())
    except Exception as e:
        logger.error(f"Error parsing ProxyResponse: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid response format from multi-turn brain endpoint: {e}"
        )
    try:
        created_dt = datetime.fromisoformat(proxy_response.timestamp)
        created_unix = int(created_dt.timestamp())
    except Exception:
        created_unix = int(datetime.now().timestamp())
    total_tokens = proxy_response.prompt_eval_count + proxy_response.eval_count
    # Note: We return the original mode string as the model for client compatibility,
    # not the underlying provider's real model name.
    chat_response = ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4()}",
        object="chat.completion",
        created=created_unix,
        model=data.model,  # <-- This is the mode, not the real model name
        choices=[
            ChatCompletionChoice(
                index=0,
                message={"role": "assistant", "content": proxy_response.response},
                finish_reason="stop"
            )
        ],
        usage=ChatUsage(
            prompt_tokens=proxy_response.prompt_eval_count,
            completion_tokens=proxy_response.eval_count,
            total_tokens=total_tokens
        )
    )
    logger.debug(f"/chat/completions Returns:\n{chat_response.model_dump_json(indent=4)}")
    return chat_response