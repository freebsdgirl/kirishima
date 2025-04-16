"""
This module provides FastAPI endpoints for handling OpenAI-compatible chat completion requests. 
It supports both special task routing and multi-turn conversation handling, ensuring compatibility 
with OpenAI's API while integrating with internal services.
Endpoints:
- `/chat/completions`: Redirects requests to the versioned `/v1/chat/completions` endpoint.
- `/v1/chat/completions`: Processes chat completion requests, supporting special task routing 
    and multi-turn conversations.
Key Features:
1. Special Task Routing:
     - Detects requests starting with "### Task" and delegates them to a completions endpoint.
     - Converts the response into a chat-compatible format.
2. Multi-Turn Conversation Handling:
     - Filters and processes user and assistant messages.
     - Forwards requests to an internal "brain" service for multi-turn conversation support.
     - Calculates token usage and formats responses to match OpenAI's API.
Dependencies:
- FastAPI for API routing and HTTP exception handling.
- httpx for asynchronous HTTP requests.
- tiktoken for token encoding and usage calculation.
- Shared models for request and response validation.
- Logging for debugging and error tracking.
Environment Variables:
- `BRAIN_HOST`: Hostname for the internal brain service (default: "brain").
- `BRAIN_PORT`: Port for the internal brain service (default: "4207").
- `BRAIN_URL`: Full URL for the brain service (default: "http://{BRAIN_HOST}:{BRAIN_PORT}").
- `SERVICE_PORT`: Port for the current service (default: "4200").

"""

from shared.models.proxy import ProxyMultiTurnRequest, ProxyResponse, ProxyMessage
from shared.models.openai import ChatMessage, ChatCompletionRequest, OpenAICompletionRequest, ChatCompletionResponse, ChatCompletionChoice, ChatUsage

import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"api.{__name__}")

import uuid
import httpx
from datetime import datetime
from transformers import AutoTokenizer

from fastapi import APIRouter, HTTPException, status, Request
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
async def chat_completions(
    req: Request,
    data: ChatCompletionRequest
):
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
    raw_body = req.state.raw_body.decode("utf-8")
    logger.debug(f"/chat/completions Request\n{raw_body}")

    #logger.info(f"/chat/completions Request\n{json.dumps(raw_body, indent=4, ensure_ascii=False)}")

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


        # Define the target completions endpoint URL.
        api_address, api_port = shared.consul.get_service_address('api')
        target_url = f"http://api:{api_port}/v1/completions"
        
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
                detail="Error converting completions response to chat format: {conversion_err}"
            )

        return chat_response

    # Normal processing for non-### Task requests:

    # Filter messages to only include 'user' and 'assistant' roles.
    filtered_messages = [
        ProxyMessage(role=msg.role, content=msg.content)
        for msg in data.messages if msg.role in ["user", "assistant"]
    ]

    proxy_request = ProxyMultiTurnRequest(
        model=data.model,
        messages=filtered_messages,
        temperature=data.temperature,
        max_tokens=data.max_tokens
    )

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            brain_address, brain_port = shared.consul.get_service_address('brain')
        
            response = await client.post(
                f"http://{brain_address}:{brain_port}/message/multiturn/incoming",
                json=proxy_request.model_dump()
            )
            response.raise_for_status()

        except Exception as e:
            logger.exception("Error retrieving service address for brain:", e)

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

    try:
        created_dt = datetime.fromisoformat(proxy_response.timestamp)
        created_unix = int(created_dt.timestamp())

    except Exception:
        created_unix = int(datetime.now().timestamp())

    prompt_text = " ".join(msg.content for msg in data.messages if msg.role in ["user", "assistant"])

    try:
        # we're hardcoding this because... there's no real good way to get around this.
        # the model name doesn't always easily translate to a tokenizer name.
        # but we're using this model for chromadb embedding, so it makes sense to use it here.
        # this is a bit of a hack, but it works for now.
        tokenizer = AutoTokenizer.from_pretrained("intfloat/e5-small-v2")
        tokens = tokenizer.encode(prompt_text)

    except Exception as err:
        logger.warning(f"Error retrieving encoding for model '{data.model}': {err}.")

        raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving encoding for model '{data.model}': {err}"
            )

    prompt_tokens = len(tokens)
    completion_tokens = proxy_response.generated_tokens
    total_tokens = prompt_tokens + completion_tokens

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
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens
        )
    )

    logger.debug(f"/chat/completions Returns:\n{chat_response.model_dump_json(indent=4)}")

    return chat_response