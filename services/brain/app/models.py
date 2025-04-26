"""
This module defines FastAPI route handlers for retrieving Ollama model information
from a proxy service. It provides endpoints to list all available models and to
fetch details for a specific model by name. The module handles communication with
the proxy service, error handling, and response validation.
Endpoints:
    - GET /models: Retrieve a list of available Ollama models.
    - GET /model/{model_name}: Retrieve details for a specific Ollama model.
Dependencies:
    - shared.config.TIMEOUT: Timeout configuration for HTTP requests.
    - shared.consul.get_service_address: Service discovery for the proxy.
    - shared.models.models.OllamaModel, OllamaModelList: Response models.
    - shared.log_config.get_logger: Logging utility.
    - httpx: Async HTTP client for proxy communication.
    - fastapi: API routing and exception handling.
    - HTTPException: For proxy service errors, connection issues, and response parsing failures.
"""

from shared.config import TIMEOUT
import shared.consul

from shared.models.models import OllamaModel, OllamaModelList

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.get("/models", response_model=OllamaModelList)
async def get_models() -> OllamaModelList:
    """
    Retrieve a list of available Ollama models from the proxy service.

    Sends a GET request to the proxy service to fetch all available models.
    Handles potential HTTP and parsing errors, returning the list of models
    or raising appropriate HTTP exceptions.

    Returns:
        OllamaModelList: A list of available Ollama models.

    Raises:
        HTTPException: If there are issues with the proxy service request or response parsing.
    """

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            proxy_address, proxy_port = shared.consul.get_service_address('proxy')
            if not proxy_address or not proxy_port:
                logger.error("Proxy service address or port is not available.")

                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Proxy service is unavailable."
                )

            response = await client.get(f"http://{proxy_address}:{proxy_port}/api/models")
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
        
        except Exception as e:
            logger.error(f"Unexpected error in proxy service: {e}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error in proxy service: {e}"
            )

    try:
        json_response = response.json()

        proxy_response = OllamaModelList.model_validate(json_response)

    except Exception as e:
        logger.error(f"Error parsing response from proxy service: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse response from proxy service: {req_err}"
        )

    return proxy_response


@router.get("/model/{model_name}", response_model=OllamaModel)
async def from_api_completions(model_name: str) -> OllamaModel:
    """
    Retrieve details for a specific Ollama model by its name.

    Sends a GET request to the proxy service to fetch model information.
    Handles potential HTTP and parsing errors, returning the model details
    or raising appropriate HTTP exceptions.

    Args:
        model_name (str): The name of the Ollama model to retrieve.

    Returns:
        OllamaModel: Detailed information about the specified model.

    Raises:
        HTTPException: If there are issues with the proxy service request or response.
    """
    logger.debug(f"/model Request: {model_name}")

    # Send the POST request using an async HTTP client
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            proxy_address, proxy_port = shared.consul.get_service_address('proxy')
            if not proxy_address or not proxy_port:
                logger.error("Proxy service address or port is not available.")

                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Proxy service is unavailable."
                )

            response = await client.get(f"http://{proxy_address}:{proxy_port}/api/models/{model_name}")
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

        except Exception as e: 
            logger.error(f"Unexpected error in proxy service: {e}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error in proxy service: {e}"
            )

    try:
        json_response = response.json()

        proxy_response = OllamaModel.model_validate(json_response)

    except Exception as e:
        logger.error(f"Error parsing response from proxy service: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse response from proxy service: {e}"
        )

    return proxy_response