"""
This module defines an API route for forwarding multi-turn conversation requests 
to an internal endpoint. It acts as a proxy without performing additional 
processing on the request or response.

Modules:
    os: Provides a way of using operating system-dependent functionality.
    httpx: An HTTP client for making asynchronous requests.
    fastapi: A modern, fast web framework for building APIs.
    shared.models.proxy: Contains the data models for the proxy request and response.
    shared.log_config: Provides a logger for structured logging.

Attributes:
    logger: A logger instance for logging debug and error messages.
    router: An APIRouter instance for defining API routes.
    proxy_host: The hostname of the proxy server, configurable via the PROXY_HOST 
                environment variable (default: "proxy").
    proxy_port: The port of the proxy server, configurable via the PROXY_PORT 
                environment variable (default: "4205").
    proxy_url: The full URL of the proxy server, constructed using the proxy_host 
               and proxy_port values.

Routes:
    @router.post("/message/multiturn/outgoing"):
        endpoint (/from/api/multiturn). It validates the response and returns it 
        to the client. If an error occurs during the forwarding process, an 
        appropriate HTTPException is raised.
"""

import app.config

from shared.models.proxy import ProxyMultiTurnRequest, ProxyResponse

from shared.log_config import get_logger
logger = get_logger(__name__)

import httpx
import os

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

# Configure the proxy URL from environment variables.
proxy_host = os.getenv("PROXY_HOST", "proxy")
proxy_port = os.getenv("PROXY_PORT", "4205")
proxy_url = os.getenv("PROXY_URL", f"http://{proxy_host}:{proxy_port}")

@router.post("/message/multiturn/incoming", response_model=ProxyResponse)
async def outgoing_multiturn_message(message: ProxyMultiTurnRequest) -> ProxyResponse:
    """
    Forwards a multi-turn conversation request to the internal multi-turn 
    endpoint (/from/api/multiturn). This endpoint acts as a simple proxy with no
    additional processing.

    Args:
        message (ProxyMultiTurnRequest): The multi-turn conversation request.

    Returns:
        ProxyResponse: The response from the internal proxy service.

    Raises:
        HTTPException: If any error occurs when contacting the proxy service.
    """
    logger.debug(f"Received multi-turn message: {message}")

    payload = message.model_dump()
    logger.debug(f"Payload for proxy service: {payload}")

    target_url = f"{proxy_url}/from/api/multiturn"

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(target_url, json=payload)
            response.raise_for_status()

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from proxy service: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error forwarding to proxy service: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error forwarding to proxy service: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )

    try:
        json_response = response.json()
        logger.debug(f"Response from proxy service: {json_response}")

        proxy_response = ProxyResponse.model_validate(json_response)

    except Exception as e:
        logger.error(f"Error parsing response from proxy service: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse response from proxy service."
        )

    logger.debug(f"Sending brain response: {proxy_response}")

    return proxy_response
