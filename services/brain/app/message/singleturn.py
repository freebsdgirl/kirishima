"""
This module defines an API endpoint for handling single-turn messages.
The endpoint receives a `ProxyOneShotRequest`, forwards it to a proxy service,
and returns the response as a `ProxyResponse`. It acts as an intermediary
service, allowing for additional scaffolding or processing if needed in the
future.
Modules and Libraries:
- `shared.config`: Provides configuration constants such as `TIMEOUT`.
- `shared.consul`: Used to retrieve the proxy service address and port.
- `shared.models.proxy`: Contains the `ProxyOneShotRequest` and `ProxyResponse` models.
- `shared.log_config`: Provides logging functionality.
- `httpx`: Used for making asynchronous HTTP requests.
- `json`: Used for JSON serialization and deserialization.
- `fastapi`: Provides the `APIRouter` and `HTTPException` for building the API.
Functions:
- `incoming_singleturn_message`: Handles POST requests to the `/message/single/incoming` endpoint.
"""
from shared.config import TIMEOUT
import shared.consul

from shared.models.proxy import ProxyOneShotRequest, ProxyResponse


from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx
import json

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
    logger.debug(f"/message/single/incoming Request:\n{message.model_dump_json(indent=4)}")

    payload = message.model_dump()
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            proxy_address, proxy_port = shared.consul.get_service_address('proxy')
            if not proxy_address or not proxy_port:
                logger.error("Proxy service address or port is not available.")

                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Proxy service is unavailable."
                )

            response = await client.post(f"http://{proxy_address}:{proxy_port}/from/api/completions", json=payload)
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
        
        except Exception as e:
            logger.error(f"Unexpected error in proxy service: {e}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error in proxy service: {e}"
            )

    try:
        json_response = response.json()
        logger.debug(f"🦙 Response from Ollama API:\n{json.dumps(json_response, indent=4, ensure_ascii=False)}")
        
        proxy_response = ProxyResponse.model_validate(json_response)

    except Exception as err:
        logger.error(f"Error parsing response from proxy service: {err}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid response format from proxy service."
        )
    
    logger.debug(f"/message/single/incoming Returns:\n{proxy_response.model_dump_json(indent=4)}")

    return proxy_response
