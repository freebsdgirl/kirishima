"""
This module provides FastAPI endpoints for handling OpenAI-compatible chat completion requests,
including multi-turn conversation support and special task routing.
Endpoints:
    - POST /chat/completions: Redirects to the versioned chat completions endpoint for compatibility.
    - POST /v1/chat/completions: Processes chat completion requests, supporting both standard multi-turn
      conversations and special task routing for prompts prefixed with '### Task'.
Key Features:
    - Redirects legacy '/chat/completions' requests to '/v1/chat/completions'.
    - Detects and routes special '### Task' prompts to a single-turn completions handler.
    - Forwards multi-turn chat requests to an internal 'brain' service for processing.
    - Calculates token usage using the tiktoken library for accurate usage reporting.
    - Returns responses formatted to match OpenAI's ChatCompletion API schema.
    - Handles and logs errors, returning appropriate HTTP status codes for various failure scenarios.
Dependencies:
    - FastAPI for API routing and response handling.
    - httpx for asynchronous HTTP requests to internal services.
    - tiktoken for token counting.
    - Shared models and configuration for request/response validation and service discovery.
"""

from shared.models.proxy import ProxyMultiTurnRequest, ProxyResponse, ChatMessage
from shared.models.openai import ChatCompletionRequest, OpenAICompletionRequest, ChatCompletionResponse, ChatCompletionChoice, ChatUsage

import shared.consul
from shared.config import TIMEOUT

from app.completions.singleturn import openai_v1_completions

from shared.log_config import get_logger
logger = get_logger(f"api.{__name__}")

import uuid
import httpx
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse
router = APIRouter()


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
#async def chat_completions(request: ChatCompletionRequest, request_data: Request) -> ChatCompletionResponse:
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
    logger.debug(f"/v1/chat/completions Request:\n{data.model_dump_json(indent=4)}")

    # Check if the first user message starts with "### Task"
    if data.messages and data.messages[0].role == "user" and data.messages[0].content.startswith("### Task"):

        # Remove the prefix and trim the remaining content.
        task_prompt = data.messages[0].content[len("### Task"):].lstrip()
        logger.debug("Detected special '### Task' prefix. Delegating request to the completions endpoint.")
        
        # Create an OpenAICompletionRequest using the shared model.
        openai_request = OpenAICompletionRequest(
            prompt=task_prompt,
            model=data.model,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            n=1  # Modify if you want multiple completions.
        )

        response = await openai_v1_completions(openai_request, None)
        completion = response.model_dump()

        # Convert the completions response into a ChatCompletionResponse.
        # This includes remapping each 'choice' to use a ChatMessage with the 'text' content.
        try:
            chat_response = ChatCompletionResponse(
                id=completion["id"],
                object="chat.completion",
                created=completion["created"],
                model=completion["model"],
                choices=[
                    ChatCompletionChoice(
                        index=choice["index"],
                        message=ChatMessage(role="assistant", content=choice["text"]),
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
                detail="Error converting completions response to chat format: {e}"
            )

        return chat_response

    # Filter messages to only include 'user' and 'assistant' roles.
    filtered_messages = [
        ChatMessage(role=msg.role, content=msg.content)
        for msg in data.messages if msg.role in ["user", "assistant", "system"]
    ]

    proxy_request = ProxyMultiTurnRequest(
        model=data.model,
        messages=filtered_messages,
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        platform='api'
    )

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            brain_address, brain_port = shared.consul.get_service_address('brain')
        
            response = await client.post(
                f"http://{brain_address}:{brain_port}/api/multiturn",
                json=proxy_request.model_dump()
            )
            response.raise_for_status()

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error forwarding to brain: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from multi-turn brain: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error when forwarding to brain: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Connection error to brain: {req_err}"
            )

        except Exception as e:
            logger.exception(f"Error retrieving service address for brain: {e}")

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error retrieving service address for brain: {e}"
            )

    try:
        proxy_response = ProxyResponse.model_validate(response.json())

    except Exception as e:
        logger.error(f"Error parsing ProxyResponse: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid response format from multi-turn brain endpoint: {e}"
        )

    try:
        created_dt = datetime.fromisoformat(proxy_response.timestamp)
        created_unix = int(created_dt.timestamp())

    except Exception:
        created_unix = int(datetime.now().timestamp())

    total_tokens = proxy_response.prompt_eval_count + proxy_response.eval_count

    chat_response = ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4()}",
        object="chat.completion",
        created=created_unix,
        model=data.model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=proxy_response.response),
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