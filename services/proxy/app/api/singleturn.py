"""
This module defines an API endpoint for handling single-turn completion requests
to a language model service. It includes the following:

- An asynchronous POST endpoint `/from/api/completions` that processes a 
    `ProxyOneShotRequest` and forwards it to the Ollama language model service.
- Constructs a payload for the external API, sends the request, and handles 
    the response.
- Returns a `ProxyResponse` containing the generated text, token count, 
    and timestamp.
- Logs detailed information for debugging purposes, including request payloads 
    and responses.
- Handles and raises appropriate HTTP exceptions for communication errors.

Dependencies:
- `app.config`: Configuration settings for the application, including the 
    `OLLAMA_URL`.
- `shared.models.proxy`: Data models for request and response payloads.
- `shared.log_config`: Logging configuration for structured and consistent logs.
- `httpx`: Asynchronous HTTP client for making API requests.
- `fastapi`: Framework for defining API routes and handling HTTP exceptions.
"""

import app.config

from shared.models.proxy import ProxyOneShotRequest, ProxyResponse

from shared.log_config import get_logger
logger = get_logger(__name__)

import httpx
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

@router.post("/from/api/completions", response_model=ProxyResponse)
async def from_api_completions(message: ProxyOneShotRequest) -> ProxyResponse:
    """
    Handle API completions request by forwarding the request to the Ollama language model service.

    This endpoint takes a ProxyOneShotRequest, constructs a payload for the Ollama API,
    sends an asynchronous request, and returns a ProxyResponse with the generated
    text and metadata.

    Args:
        message (ProxyOneShotRequest): The completion request containing model, prompt,
            temperature, and max tokens parameters.

    Returns:
        ProxyResponse: The response from the language model, including generated
            text, token count, and timestamp.

    Raises:
        HTTPException: If there are connection or communication errors with the Ollama service.
    """
    logger.debug(f"Received API completions request: {message}")

    # Construct the payload for the Ollama API request
    payload = {
        "model": message.model,
        "prompt": message.prompt,
        "temperature": message.temperature,
        "max_tokens": message.max_tokens,
        "stream": False
    }

    logger.debug(f"Constructed payload for Ollama API: {payload}")

    # Send the POST request using an async HTTP client
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{app.config.OLLAMA_URL}/api/generate", json=payload)
            response.raise_for_status()

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error occurred: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"An error occurred when communicating with the language model service: {req_err}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error occurred: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to connect to the language model service: {req_err}"
            )

    # Log the raw response from the Ollama API
    json_response = response.json()
    logger.debug(f"Response from Ollama API: {json_response}")

    # Construct the ProxyResponse from the API response data
    proxy_response = ProxyResponse(
        response=json_response.get("response"),
        generated_tokens=json_response.get("eval_count"),
        timestamp=datetime.now().isoformat()
    )

    logger.debug(f"Sending API completions response: {proxy_response}")
    return proxy_response