"""
This module defines API endpoints for handling requests related to proxy services.

Endpoints:
- `/from/api`: Processes a `ProxyRequest` by constructing a system prompt, extracting
    the last user message, building an OpenAI-compatible payload, and sending it to a
    language model. Returns a dictionary with the response status, generated reply,
    and raw output.
- `/from/api/completions`: Handles a `ProxyOneShotRequest` by forwarding the request
    to the Ollama language model service. Constructs a payload, sends an asynchronous
    request, and returns a `ProxyOneShotResponse` with the generated text and metadata.

Dependencies:
- `app.config`: Configuration settings for the application.
- `shared.models.proxy`: Data models for proxy-related requests and responses.
- `app.prompts.dispatcher`: Utility for constructing system prompts.
- `app.util`: Helper functions for processing messages and sending payloads.
- `shared.log_config`: Logger configuration for structured logging.
- `httpx`: Asynchronous HTTP client for making API requests.
- `fastapi`: Framework for building API routes and handling HTTP exceptions.

Logging:
- Logs are generated for debugging purposes, including received requests, constructed
    payloads, and responses from external services.

Error Handling:
- Validates incoming request data and handles errors related to missing or invalid
    fields.
- Catches HTTP and connection errors when communicating with external services and
    raises appropriate HTTP exceptions.
"""

import app.config

from app.prompts.dispatcher import get_prompt_builder
from app.util import send_openai_payload_to_llm, strip_to_last_user

from shared.models.proxy import ProxyRequest, ProxyOneShotRequest, ProxyOneShotResponse

from shared.log_config import get_logger
logger = get_logger(__name__)

import httpx
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/from/api", response_model=dict)
async def from_api(message: ProxyRequest) -> dict:
    """
    Handles POST requests to the "/from/api" endpoint by processing a ProxyRequest.

    Constructs a system prompt, extracts the last user message, builds an OpenAI-compatible
    payload, and sends it to a language model. Returns a dictionary with the response status,
    generated reply, and raw output.

    Args:
        message (ProxyRequest): The incoming request containing mode, memories, and message metadata.

    Returns:
        dict: A response containing 'status', 'reply', and optional 'raw' keys from the language model.
        Returns an error dictionary if message validation fails.
    """
    logger.debug(f"Received API request: {message}")

    # Step 1: Build the system prompt
    builder = get_prompt_builder(message.mode, message.memories)
    system_prompt = builder(message)
    logger.debug(f"Constructed system prompt: {system_prompt}")

    # Step 2: Extract OpenAI-style messages
    messages = message.message.metadata.get("messages")
    if not isinstance(messages, list):
        logger.error("Invalid or missing 'messages' in metadata.")

        return {
            "error": "Invalid or missing 'messages' list in metadata."
        }

    # Step 3: Get last user message
    last_user_msg = strip_to_last_user(messages)
    if not last_user_msg:
        logger.error("No user message found in 'messages'.")

        return {
            "error": "No user message found in 'messages'."
        }

    logger.debug(f"Last user message: {last_user_msg}")

    # Step 4: Build OpenAI payload
    payload = {
        "model": app.config.LLM_MODEL_NAME,
        "messages": [
            {
                "role": "system", "content": system_prompt
            },
            last_user_msg
        ]
    }

    logger.debug(f"Sending payload to LLM: {payload}")

    # Step 5: Send to LLM
    response =  await send_openai_payload_to_llm(payload)
    logger.debug(f"LLM response: {response}")

    return {
        "status": "success",
        "reply": response.get("reply", ""),
        "raw": response.get("raw")
    }


@router.post("/from/api/completions", response_model=ProxyOneShotResponse)
async def from_api_completions(message: ProxyOneShotRequest) -> ProxyOneShotResponse:
    """
    Handle API completions request by forwarding the request to the Ollama language model service.

    This endpoint takes a ProxyOneShotRequest, constructs a payload for the Ollama API,
    sends an asynchronous request, and returns a ProxyOneShotResponse with the generated
    text and metadata.

    Args:
        message (ProxyOneShotRequest): The completion request containing model, prompt,
            temperature, and max tokens parameters.

    Returns:
        ProxyOneShotResponse: The response from the language model, including generated
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

    # Construct the ProxyOneShotResponse from the API response data
    proxy_response = ProxyOneShotResponse(
        response=json_response.get("response"),
        generated_tokens=json_response.get("eval_count"),
        timestamp=datetime.now().isoformat()
    )

    logger.debug(f"Sending API completions response: {proxy_response}")
    return proxy_response