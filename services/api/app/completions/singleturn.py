"""
This module provides FastAPI endpoints for handling OpenAI-style text completion requests. 
It includes functionality to redirect requests to a versioned endpoint and to process 
completion requests by proxying them to an internal service.
Endpoints:
    - POST /completions: Redirects to /v1/completions.
    - POST /v1/completions: Processes OpenAI-style completion requests and returns responses 
      in the OpenAI format.
Functions:
    openai_completions(request: OpenAICompletionRequest) -> RedirectResponse:
    openai_v1_completions(request: OpenAICompletionRequest) -> OpenAICompletionResponse:
        Handles OpenAI-style completion requests by proxying them to an internal service. 
        Supports sequential execution of multiple requests based on the `n` parameter and 
        aggregates responses into the OpenAI format.
Dependencies:
    - FastAPI for API routing and HTTP exception handling.
    - httpx for making asynchronous HTTP requests to the proxy service.
    - tiktoken for tokenizing prompts and calculating token usage.
    - Pydantic models for request validation and response formatting.
    - dateutil for parsing ISO 8601 timestamps.
    - Logging for tracking request and response data.
Environment Variables:
    - BRAIN_HOST: Hostname of the internal proxy service (default: "brain").
    - BRAIN_PORT: Port of the internal proxy service (default: "4207").
    - BRAIN_URL: Full URL of the internal proxy service (default: "http://{BRAIN_HOST}:{BRAIN_PORT}").
Notes:
    - The '/v1/completions' endpoint logs all incoming requests and responses for debugging purposes.
    - The proxy service is expected to return responses in a specific format, which are validated 
      using the ProxyResponse model.
    - The system calculates token usage for both prompts and completions to provide detailed usage 
      statistics in the response.
"""

from shared.models.proxy import ProxyResponse
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
    proxy service (/from/api/completions). All incoming request data is logged.
    
    If the request includes the parameter `n`, the proxy call is executed sequentially
    that many times. The response is then aggregated to simulate an OpenAI completions
    response format, which includes a usage section detailing prompt and completion tokens.

    Args:
        request (OpenAICompletionRequest): The OpenAI-style request with a required prompt.

    Returns:
        OpenAICompletionResponse: A simulated OpenAI completions response.
    """
    raw_body = await request_data.json()
    logger.info(f"/completions Request:\n{json.dumps(raw_body, indent=4, ensure_ascii=False)}")

    n = request.n if request.n and request.n > 0 else 1
    completions: List[OpenAICompletionChoice] = []
    total_completion_tokens = 0
    created_unix: Optional[int] = None

    # Prepare data to send to the proxy service. Include stream: False to avoid streaming responses.
    proxy_request_data = {
        "prompt": request.prompt,
        "model": request.model,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "stream": False,
    }

    # Sequentially call the proxy service n times
    async with httpx.AsyncClient(timeout=60) as client:
        for i in range(n):
            try:
                brain_address, brain_port = get_service_address('brain')
                response = await client.post(
                    f"http://{brain_address}:{brain_port}/message/single/incoming", 
                    json=proxy_request_data
                )
                response.raise_for_status()

            except httpx.HTTPStatusError as http_err:
                logger.error(f"HTTP error from proxy service: {http_err.response.status_code} - {http_err.response.text}")
                raise HTTPException(
                    status_code=http_err.response.status_code,
                    detail=f"Error from proxy service: {http_err.response.text}"
                )

            except httpx.RequestError as req_err:
                logger.error(f"Request error connecting to proxy service: {req_err}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Connection error: {req_err}"
                )

            json_response = response.json()

            try:
                # Use model_validate per Pydantic v2 practices (replacing deprecated parse_obj)
                proxy_response = ProxyResponse.model_validate(json_response)

            except Exception as err:
                logger.error(f"Error parsing response from proxy service: {err}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid response format from proxy service."
                )

            # For the first call, derive the created timestamp (convert ISO 8601 to UNIX time)
            if created_unix is None:
                try:
                    dt = parser.isoparse(proxy_response.timestamp)
                    created_unix = int(dt.timestamp())

                except Exception as err:
                    logger.error(f"Error converting timestamp: {err}")
                    created_unix = int(datetime.datetime.now().timestamp())

            total_completion_tokens += proxy_response.generated_tokens

            # Create an OpenAI-style choice from the proxy response
            choice = OpenAICompletionChoice(
                text=proxy_response.response,
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

    logger.debug(f"/completions Returns:\n{openai_response.model_dump_json(indent=4)}")

    return openai_response
