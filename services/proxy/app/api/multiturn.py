"""
This module defines an API endpoint for handling multi-turn conversation requests.
The `/api/multiturn` endpoint processes requests to generate responses for multi-turn
conversations using a language model. It validates the request, constructs a system
prompt, builds an instruct-style prompt, and communicates with the Ollama API to
generate a response. The endpoint returns the generated response along with metadata.
Modules:
    - shared.config: Provides configuration constants such as TIMEOUT.
    - shared.models.proxy: Defines data models for ProxyRequest, ChatMessages, etc.
    - app.util: Contains utility functions for building prompts.
    - app.config: Application-specific configuration.
    - shared.log_config: Provides logging configuration.
    - httpx: Used for making asynchronous HTTP requests.
    - json: Used for JSON serialization and deserialization.
    - datetime, dateutil.tz: Used for handling timestamps with timezone information.
    - fastapi: Provides the APIRouter and HTTPException classes for API routing and error handling.
Functions:
    - from_api_multiturn(request: ProxyMultiTurnRequest) -> ProxyResponse:
        Handles multi-turn API requests by generating prompts for language models.
"""
from shared.config import TIMEOUT
from shared.models.proxy import ProxyRequest, ChatMessages, IncomingMessage, ProxyMultiTurnRequest, ProxyResponse

from app.util import build_multiturn_prompt
from app.prompts.dispatcher import get_system_prompt
import app.config

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


@router.post("/api/multiturn", response_model=ProxyResponse)
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

    logger.debug(f"/api/multiturn Request:\n{request.model_dump_json(indent=4)}")

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
        memories=request.memories,
        summaries=request.summaries,
        mode='nsfw'
    )

    # now get your dynamic system prompt
    system_prompt = get_system_prompt(proxy_req)

    # 4) build the full instruct‑style prompt
    full_prompt = build_multiturn_prompt(ChatMessages(messages=request.messages), system_prompt)

    # Construct the payload for the Ollama API call
    payload = {
        "model": request.model,
        "prompt": full_prompt,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "stream": False,
        "raw": True
    }

    logger.debug(f"🦙 Request to Ollama API:\n{json.dumps(payload, indent=4, ensure_ascii=False)}")

    # Send the POST request using an async HTTP client
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
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
        
        except Exception as e:
            logger.error(f"Unexpected error in Ollama API: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error in language model service: {e}"
            )

    try:
        json_response = response.json()
        logger.debug(f"🦙 Response from Ollama API:\n{json.dumps(json_response, indent=4, ensure_ascii=False)}")

        # Construct the ProxyResponse from the API response data.
        proxy_response = ProxyResponse(
            response=json_response.get("response"),
            generated_tokens=json_response.get("eval_count"),
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Error parsing response from Ollama API: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse response from Ollama API: {e}"
        )

    logger.debug(f"/api/multiturn Response:\n{proxy_response.model_dump_json(indent=4)}")

    return proxy_response
