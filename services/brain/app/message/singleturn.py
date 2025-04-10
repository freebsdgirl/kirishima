"""
This module defines an API endpoint for handling single-turn messages by proxying
them to an external service. It provides scaffolding for potential future extensions
and ensures proper logging and error handling.
Modules:
    - shared.models.proxy: Contains the ProxyOneShotRequest and ProxyOneShotResponse models.
    - shared.log_config: Provides the logging configuration.
    - fastapi: Used for creating the API endpoint and handling HTTP exceptions.
    - httpx: Used for making asynchronous HTTP requests.
    - os: Used for accessing environment variables.
Environment Variables:
    - PROXY_HOST: The hostname of the proxy service (default: "proxy").
    - PROXY_PORT: The port of the proxy service (default: "4205").
    - PROXY_URL: The full URL of the proxy service. If not provided, it is constructed
      using PROXY_HOST and PROXY_PORT.
Functions:
    - incoming_singleturn_message(message: ProxyOneShotRequest) -> ProxyOneShotResponse:
        Handles incoming single-turn messages by forwarding them to the proxy service
        and returning the response. Includes detailed logging and error handling.
"""

from shared.models.proxy import ProxyOneShotRequest, ProxyOneShotResponse

from shared.log_config import get_logger
logger = get_logger(__name__)

import httpx
import os

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

# Configure proxy URL from environment variables
proxy_host = os.getenv("PROXY_HOST", "proxy")
proxy_port = os.getenv("PROXY_PORT", "4205")
proxy_url = os.getenv("PROXY_URL", f"http://{proxy_host}:{proxy_port}")

@router.post("/single/incoming", response_model=ProxyOneShotResponse)
async def incoming_singleturn_message(message: ProxyOneShotRequest) -> ProxyOneShotResponse:
    """
    Proxies the incoming single-turn message to the proxy service.
    
    This function receives a ProxyOneShotRequest, forwards it to the proxy service,
    and returns the response as a ProxyOneShotResponse. This intermediary service
    allows for additional scaffolding if needed in the future.
    
    Args:
        message (ProxyOneShotRequest): The incoming request payload.
    
    Returns:
        ProxyOneShotResponse: The response received from the proxy service.
    
    Raises:
        HTTPException: If any error occurs when contacting the proxy service.
    """
    logger.debug(f"Received single-turn message: {message}")

    payload = message.model_dump()
    logger.debug(f"Payload for proxy service: {payload}")

    target_url = f"{proxy_url}/from/api/completions"
    
    async with httpx.AsyncClient() as client:
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
        
        proxy_response = ProxyOneShotResponse.model_validate(json_response)

    except Exception as err:
        logger.error(f"Error parsing response from proxy service: {err}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid response format from proxy service."
        )

    logger.debug(f"Sending brain response: {proxy_response}")

    return proxy_response
