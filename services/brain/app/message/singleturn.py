"""
This module defines an API endpoint for handling single-turn messages.
The endpoint receives a `ProxyOneShotRequest`, forwards it to a proxy service,
and returns the response as a `ProxyResponse`. It acts as an intermediary layer
to facilitate communication with the proxy service, allowing for future
enhancements or additional processing.
Modules:
    app.config: Configuration settings for the application.
    shared.models.proxy: Contains the `ProxyOneShotRequest` and `ProxyResponse` models.
    shared.log_config: Provides logging functionality.
    httpx: For making asynchronous HTTP requests.
    fastapi: Framework for building API endpoints.
Attributes:
    logger: Logger instance for logging debug and error messages.
    router: FastAPI APIRouter instance for defining API routes.
Routes:
    POST /message/single/incoming:
        - Receives a `ProxyOneShotRequest` payload.
        - Forwards the payload to the proxy service.
        - Returns the response as a `ProxyResponse`.
        - Handles HTTP and connection errors gracefully.
"""

from shared.models.proxy import ProxyOneShotRequest, ProxyResponse

import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/message/single/incoming", response_model=ProxyResponse)
async def incoming_singleturn_message(message: ProxyOneShotRequest) -> ProxyResponse:
    """
    Proxies the incoming single-turn message to the proxy service.
    
    This function receives a ProxyOneShotRequest, forwards it to the proxy service,
    and returns the response as a ProxyResponse. This intermediary service
    allows for additional scaffolding if needed in the future.
    
    Args:
        message (ProxyOneShotRequest): The incoming request payload.
    
    Returns:
        ProxyResponse: The response received from the proxy service.
    
    Raises:
        HTTPException: If any error occurs when contacting the proxy service.
    """
    logger.debug(f"Received single-turn message: {message}")

    payload = message.model_dump()
    logger.debug(f"Payload for proxy service: {payload}")

    target_url = f"http://{shared.consul.proxy_address}:{shared.consul.proxy_port}/from/api/completions"
    
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(target_url, json=payload)
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

    try:
        json_response = response.json()
        logger.debug(f"Response from proxy service: {json_response}")
        
        proxy_response = ProxyResponse.model_validate(json_response)

    except Exception as err:
        logger.error(f"Error parsing response from proxy service: {err}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid response format from proxy service."
        )

    logger.debug(f"Sending brain response: {proxy_response}")

    return proxy_response
