"""
This module defines the FastAPI router and endpoint for handling single-turn completion
requests to a language model service (Ollama) via a proxy API.
It provides the following functionality:
- Receives a ProxyOneShotRequest containing model parameters and prompt.
- Forwards the request to the Ollama API using an asynchronous HTTP client.
- Handles and logs HTTP and connection errors, returning appropriate HTTPException responses.
- Parses the Ollama API response and constructs a ProxyResponse containing the generated text,
    token count, and timestamp.
- Logs both the incoming request and outgoing response for debugging and traceability.
Dependencies:
- FastAPI for API routing and exception handling.
- httpx for asynchronous HTTP requests.
- shared.models.proxy for request/response models.
- shared.log_config for logging.
- app.config for configuration values (e.g., OLLAMA_URL).
"""

import app.config
from shared.config import TIMEOUT

from shared.models.proxy import ProxyOneShotRequest, ProxyResponse, OllamaRequest, OllamaResponse

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

import httpx
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

@router.post("/api/singleturn", response_model=ProxyResponse)
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
    logger.debug(f"/api/singleturn Request:\n{message.model_dump_json(indent=4)}")

    # Construct the payload for the Ollama API request
    payload = OllamaRequest(
        model=message.model,
        prompt=message.prompt,
        temperature=message.temperature,
        max_tokens=message.max_tokens,
        stream=False,
        raw=True
    )

    logger.debug(f"🦙 Request to Ollama API:\n{json.dumps(payload.model_dump(), indent=4, ensure_ascii=False)}")

    # Send the POST request using an async HTTP client
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.post(f"{app.config.OLLAMA_URL}/api/generate", json=payload.model_dump())
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
        
        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {e}"
            )

    try:
        # Log the raw response from the Ollama API
        json_response = response.json()
        logger.debug(f"🦙 Response from Ollama API:\n{json.dumps(json_response, indent=4, ensure_ascii=False)}")

        # Construct the ProxyResponse from the API response data
        ollama_response = OllamaResponse(**json_response)
        proxy_response = ProxyResponse(
            response=ollama_response.response,
            eval_count=ollama_response.eval_count,
            prompt_eval_count=ollama_response.prompt_eval_count,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Error parsing response from Ollama API: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse response from the language model service: {e}"
        )

    return proxy_response