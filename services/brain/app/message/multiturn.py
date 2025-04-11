"""
This module defines an API endpoint for handling multi-turn conversation requests 
and forwarding them to an internal proxy service. It acts as a simple proxy 
without additional processing.

Modules:
    app.config: Provides configuration settings for the application.
    shared.models.proxy: Contains data models for ProxyMultiTurnRequest and ProxyResponse.
    shared.log_config: Provides a logger for logging messages.
    httpx: Used for making asynchronous HTTP requests.
    fastapi: Provides tools for building API routes and handling HTTP exceptions.

Classes:
    None

Functions:
    outgoing_multiturn_message(message: ProxyMultiTurnRequest) -> ProxyResponse:
        Handles incoming multi-turn conversation requests, forwards them to the 
        internal proxy service, and returns the response.

Dependencies:
    - app.config.PROXY_URL: The base URL for the proxy service.
    - ProxyMultiTurnRequest: The request model for multi-turn conversations.
    - ProxyResponse: The response model for multi-turn conversations.
    - httpx.AsyncClient: Used for making asynchronous HTTP requests.
    - fastapi.APIRouter: Used for defining API routes.
    - fastapi.HTTPException: Used for raising HTTP exceptions.
"""

import app.config

from shared.models.proxy import ProxyMultiTurnRequest, ProxyResponse

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


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

    target_url = f"{app.config.PROXY_URL}/from/api/multiturn"

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
