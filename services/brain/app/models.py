"""
This module defines FastAPI routes for interacting with Ollama models through a proxy service.

Routes:
    - GET /models: Retrieves a list of available Ollama models.
    - GET /model/{model_name}: Retrieves details for a specific Ollama model by its name.

Functions:
    - get_models: Fetches a list of available Ollama models from the proxy service.
    - from_api_completions: Fetches details for a specific Ollama model by its name.

Dependencies:
    - app.config: Contains application configuration, including the proxy service URL.
    - shared.models.models: Provides the OllamaModel and OllamaModelList schemas.
    - shared.log_config: Configures logging for the module.
    - httpx: Used for making asynchronous HTTP requests.
    - fastapi: Provides the APIRouter and HTTPException classes for defining routes and handling errors.

Logging:
    - Logs debug messages for incoming requests, responses from the proxy service, and outgoing responses.
    - Logs errors for HTTP and request issues, as well as response parsing errors.

Error Handling:
    - Raises HTTPException for HTTP errors, request errors, and response parsing issues.
"""

from shared.models.models import OllamaModel, OllamaModelList

import shared.consul

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
    logger.debug(f"/models Request")

    async with httpx.AsyncClient(timeout=60) as client:
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

    try:
        json_response = response.json()

        proxy_response = OllamaModelList.model_validate(json_response)

    except Exception as e:
        logger.error(f"Error parsing response from proxy service: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse response from proxy service: {req_err}"
        )

    logger.debug(f"/models Returns:\n{proxy_response.model_dump_json(indent=4)}")

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
    async with httpx.AsyncClient(timeout=60) as client:
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

    try:
        json_response = response.json()

        proxy_response = OllamaModel.model_validate(json_response)

    except Exception as e:
        logger.error(f"Error parsing response from proxy service: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse response from proxy service: {req_err}"
        )

    logger.debug(f"/model Returns:\n{proxy_response.model_dump_json(indent=4)}")

    return proxy_response