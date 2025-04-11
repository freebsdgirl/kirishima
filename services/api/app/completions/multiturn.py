"""
This module provides FastAPI endpoints and data models for handling OpenAI-compatible chat completion requests.
The main functionalities include:
1. Defining Pydantic models for request and response structures, such as `ChatMessage`, `ChatCompletionRequest`, 
    `ChatCompletionResponse`, and related components.
2. Implementing endpoints for redirecting and processing chat completion requests:
    - `/chat/completions`: Redirects to `/v1/chat/completions`.
    - `/v1/chat/completions`: Processes chat completion requests by forwarding them to an internal multi-turn brain endpoint.
3. Logging and error handling for incoming requests and responses.
Classes:
- `ChatMessage`: Represents a single message in a chat conversation.
- `ChatCompletionRequest`: Represents the structure of a chat completion request.
- `ChatCompletionChoice`: Represents an individual choice in the chat completion response.
- `ChatUsage`: Represents token usage statistics for a chat completion.
- `ChatCompletionResponse`: Represents the structure of a chat completion response.
Endpoints:
- `openai_completions`: Redirects requests from `/chat/completions` to `/v1/chat/completions`.
- `chat_completions`: Handles chat completion requests by forwarding them to an internal service and returning a formatted response.
Environment Variables:
- `BRAIN_HOST`: Hostname for the internal multi-turn brain service (default: "brain").
- `BRAIN_PORT`: Port for the internal multi-turn brain service (default: "4207").
- `BRAIN_URL`: Full URL for the internal multi-turn brain service (default: "http://{BRAIN_HOST}:{BRAIN_PORT}").
Dependencies:
- `httpx`: For making asynchronous HTTP requests.
- `fastapi`: For defining API routes and handling HTTP requests.
- `pydantic`: For data validation and serialization.
- `shared.models.proxy`: For internal proxy request and response models.
- `shared.log_config`: For logging configuration.
Error Handling:
- Handles HTTP and request errors when communicating with the internal multi-turn brain service.
- Validates and parses responses from the internal service, raising HTTP exceptions for invalid formats.
Logging:
- Logs incoming requests, filtered messages, and outgoing responses for debugging and traceability.
"""

from shared.models.proxy import ProxyMultiTurnRequest, ProxyResponse, ProxyMessage
from shared.models.openai import ChatMessage, ChatCompletionRequest, OpenAICompletionRequest, ChatCompletionResponse, ChatCompletionChoice, ChatUsage

from shared.log_config import get_logger
logger = get_logger(f"api.{__name__}")

import uuid
import httpx
from datetime import datetime
import tiktoken

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse
router = APIRouter()

import os
brain_host = os.getenv("BRAIN_HOST", "brain")
brain_port = os.getenv("BRAIN_PORT", "4207")
brain_url = os.getenv("BRAIN_URL", f"http://{brain_host}:{brain_port}")
service_port = os.getenv("SERVICE_PORT", "4200")

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


@router.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest) -> ChatCompletionResponse:
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
    logger.info(f"Received OpenAI chat completion request: {request.dict()}")

    # Check if the first user message starts with "### Task"
    if request.messages and request.messages[0].role == "user" and request.messages[0].content.startswith("### Task"):
        # Remove the prefix and trim the remaining content.
        task_prompt = request.messages[0].content[len("### Task"):].lstrip()
        logger.info("Detected special '### Task' prefix. Delegating request to the completions endpoint.")
        
        # Create an OpenAICompletionRequest using the shared model.
        openai_request = OpenAICompletionRequest(
            prompt=task_prompt,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            n=1  # Modify if you want multiple completions.
        )

        # Define the target completions endpoint URL.
        target_url = f"http://api:4200/v1/completions"
        
        async with httpx.AsyncClient() as client:
            try:
                comp_response = await client.post(target_url, json=openai_request.model_dump())
                comp_response.raise_for_status()
            except httpx.HTTPStatusError as http_err:
                logger.error(f"HTTP error calling completions endpoint: {http_err.response.status_code} - {http_err.response.text}")
                raise HTTPException(
                    status_code=http_err.response.status_code,
                    detail=f"Error from completions endpoint: {http_err.response.text}"
                )
            except httpx.RequestError as req_err:
                logger.error(f"Request error when calling completions endpoint: {req_err}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Connection error: {req_err}"
                )
        
        # Retrieve the completions response JSON.
        comp_json = comp_response.json()

        # Convert the completions response into a ChatCompletionResponse.
        # This includes remapping each 'choice' to use a ChatMessage with the 'text' content.
        try:
            chat_response = ChatCompletionResponse(
                id=comp_json["id"],
                object="chat.completion",
                created=comp_json["created"],
                model=comp_json["model"],
                choices=[
                    ChatCompletionChoice(
                        index=choice["index"],
                        message=ChatMessage(role="assistant", content=choice["text"]),
                        finish_reason=choice.get("finish_reason", "stop")
                    )
                    for choice in comp_json.get("choices", [])
                ],
                usage=ChatUsage(
                    prompt_tokens=comp_json["usage"]["prompt_tokens"],
                    completion_tokens=comp_json["usage"]["completion_tokens"],
                    total_tokens=comp_json["usage"]["total_tokens"]
                )
            )
        except Exception as conversion_err:
            logger.error(f"Error converting completions response to chat format: {conversion_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error processing completions response."
            )
        
        return chat_response

    # Normal processing for non-### Task requests:

    # Filter messages to only include 'user' and 'assistant' roles.
    filtered_messages = [
        ProxyMessage(role=msg.role, content=msg.content)
        for msg in request.messages if msg.role in ["user", "assistant"]
    ]

    proxy_request = ProxyMultiTurnRequest(
        model=request.model,
        messages=filtered_messages,
        temperature=request.temperature,
        max_tokens=request.max_tokens
    )

    target_url = f"{brain_url}/message/multiturn/incoming"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(target_url, json=proxy_request.model_dump())
            response.raise_for_status()
        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error forwarding to multi-turn endpoint: {http_err.response.status_code} - {http_err.response.text}")
            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from multi-turn brain: {http_err.response.text}"
            )
        except httpx.RequestError as req_err:
            logger.error(f"Request error when forwarding to multi-turn endpoint: {req_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )

    try:
        proxy_response = ProxyResponse.model_validate(response.json())
    except Exception as err:
        logger.error(f"Error parsing ProxyResponse: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid response format from multi-turn brain endpoint."
        )

    logger.info(f"Received ProxyResponse: {proxy_response}")

    try:
        created_dt = datetime.fromisoformat(proxy_response.timestamp)
        created_unix = int(created_dt.timestamp())
    except Exception:
        created_unix = int(datetime.now().timestamp())

    prompt_text = " ".join(msg.content for msg in request.messages if msg.role in ["user", "assistant"])
    try:
        encoding = tiktoken.encoding_for_model(request.model)
    except Exception as err:
        logger.warning(f"Error retrieving encoding for model '{request.model}': {err}. Falling back to default encoding.")
        encoding = tiktoken.get_encoding("gpt2")
    prompt_tokens = len(encoding.encode(prompt_text))
    completion_tokens = proxy_response.generated_tokens
    total_tokens = prompt_tokens + completion_tokens

    chat_response = ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4()}",
        object="chat.completion",
        created=created_unix,
        model=request.model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=proxy_response.response),
                finish_reason="stop"
            )
        ],
        usage=ChatUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens
        )
    )

    logger.info(f"Returning OpenAI chat completion response: {chat_response.dict()}")
    return chat_response