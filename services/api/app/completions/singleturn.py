"""
This module defines FastAPI endpoints for handling OpenAI-style single-turn completion requests.
Endpoints:
    - POST /completions: Redirects to the versioned endpoint /v1/completions for backward compatibility.
    - POST /v1/completions: Accepts OpenAICompletionRequest objects, proxies the request to an internal brain service,
      aggregates responses if multiple completions are requested, and returns an OpenAICompletionResponse in the
      expected OpenAI API format.
Key Features:
    - Logs all incoming request data for auditing and debugging.
    - Supports multiple completions per request by sequentially calling the proxy service.
    - Aggregates token usage statistics and formats the response to match OpenAI's API.
    - Handles errors from the proxy service and service discovery gracefully, returning appropriate HTTP errors.
    - Uses tiktoken for accurate prompt token counting.
"""

from shared.models.proxy import ProxyResponse, ProxyOneShotRequest
from shared.models.openai import OpenAICompletionRequest, OpenAICompletionResponse, OpenAICompletionChoice, OpenAIUsage

from shared.consul import get_service_address

from shared.log_config import get_logger
logger = get_logger(f"api.{__name__}")

import uuid
import datetime
import json
import httpx
from dateutil import parser
from typing import Optional, List
import tiktoken

from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import RedirectResponse
router = APIRouter()

with open('/app/shared/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


@router.post("/completions", response_model=OpenAICompletionResponse)
async def openai_completions(request: OpenAICompletionRequest) -> RedirectResponse:
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
        url="/v1/completions",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )


@router.post("/v1/completions", response_model=OpenAICompletionResponse)
async def openai_v1_completions(request: OpenAICompletionRequest, request_data: Request) -> OpenAICompletionResponse:
    """
    Handles an OpenAI-style completions request and proxies it to the internal
    proxy service (/api/singleturn). All incoming request data is logged.
    
    If the request includes the parameter `n`, the proxy call is executed sequentially
    that many times. The response is then aggregated to simulate an OpenAI completions
    response format, which includes a usage section detailing prompt and completion tokens.

    Args:
        request (OpenAICompletionRequest): The OpenAI-style request with a required prompt.

    Returns:
        OpenAICompletionResponse: A simulated OpenAI completions response.
    """
    # PATCH: Fix NoneType error by making request_data optional and using request only if present
    raw_body = await request_data.json() if request_data is not None else request.model_dump()
    logger.info(f"/v1/completions Request:\n{json.dumps(raw_body, indent=4, ensure_ascii=False)}")

    n = request.n if request.n and request.n > 0 else 1
    completions: List[OpenAICompletionChoice] = []
    total_completion_tokens = 0
    created_unix: Optional[int] = None

    # Prepare data to send to the proxy service using ProxyOneShotRequest for validation.
    proxy_request = ProxyOneShotRequest(
        prompt=request.prompt,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        provider=request.provider
    )
    proxy_request_data = proxy_request.model_dump()
    proxy_request_data["stream"] = False

    # Sequentially call the proxy service n times
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for i in range(n):
            try:
                brain_address, brain_port = get_service_address('brain')
                response = await client.post(
                    f"http://{brain_address}:{brain_port}/api/singleturn", 
                    json=proxy_request_data
                )
                response.raise_for_status()

            except httpx.HTTPStatusError as http_err:
                logger.error(f"HTTP error from brain service: {http_err.response.status_code} - {http_err.response.text}")
                raise HTTPException(
                    status_code=http_err.response.status_code,
                    detail=f"Error from brain service: {http_err.response.text}"
                )

            except httpx.RequestError as req_err:
                logger.error(f"Request error connecting to brain service: {req_err}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Connection error: {req_err}"
                )

            except Exception as e:
                logger.exception(f"Error retrieving service address for brain: {e}")

                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Error retrieving service address for brain: {e}"
                )

            proxy_response = ProxyResponse(**response.json())

            # For the first call, derive the created timestamp (convert ISO 8601 to UNIX time)
            try:
                dt = parser.isoparse(proxy_response.timestamp)
                created_unix = int(dt.timestamp())

            except Exception as err:
                logger.error(f"Error converting timestamp: {err}")
                created_unix = int(datetime.datetime.now().timestamp())

            total_completion_tokens += proxy_response.eval_count

            # Create an OpenAI-style choice from the proxy response
            choice = OpenAICompletionChoice(
                content=proxy_response.response,
                index=i,
                logprobs=None,
                finish_reason="stop"
            )
            completions.append(choice)

    try:
        # Use tiktoken with gpt2 encoding to count prompt tokens
        encoding = tiktoken.get_encoding("gpt2")
        tokens = encoding.encode(request.prompt)

    except Exception as err:
        logger.warning(f"Error retrieving encoding for model '{request.model}': {err}.")
        raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving encoding for model '{request.model}': {err}"
            )

    prompt_tokens = len(tokens)
    total_tokens = prompt_tokens + total_completion_tokens

    # Construct the final OpenAI completions response
    openai_response = OpenAICompletionResponse(
        id=f"cmpl-{uuid.uuid4()}",
        object="text_completion",
        created=created_unix if created_unix else int(datetime.datetime.now().timestamp()),
        model=request.model,
        choices=completions,
        usage=OpenAIUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=total_completion_tokens,
            total_tokens=total_tokens
        ),
        system_fingerprint="kirishima"
    )

    logger.debug(f"/v1/completions Returns:\n{openai_response.model_dump_json(indent=4)}")

    return openai_response
