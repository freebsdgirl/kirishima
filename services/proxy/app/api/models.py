"""
This module defines API endpoints for interacting with the Ollama API to retrieve
information about available models and specific model details.

Endpoints:
    - GET /models: Retrieves a list of available Ollama models.
    - GET /models/{model_name}: Retrieves details for a specific Ollama model.

Dependencies:
    - app.config: Contains configuration settings, including the base URL for the Ollama API.
    - shared.models.models: Defines the `OllamaModel` and `OllamaModelList` schemas.
    - shared.log_config: Provides a logger for logging errors and information.
    - httpx: Used for making asynchronous HTTP requests.
    - fastapi: Provides the `APIRouter`, `HTTPException`, and `status` utilities.

Functions:
    - list_models: Fetches a list of available Ollama models from the Ollama API.
    - get_model: Fetches details for a specific Ollama model by its name.

    - HTTPException: Raised with a 502 Bad Gateway status code if there is an error
      communicating with the Ollama API.
"""

import app.config

from shared.models.models import OllamaModel, OllamaModelList

from shared.log_config import get_logger
logger = get_logger(__name__)

import httpx
from fastapi import HTTPException, status, APIRouter
from typing import List

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.get("/api/models", response_model=OllamaModelList)
async def list_models() -> OllamaModelList:
    """
    Retrieves a list of all models from the Ollama API.
    
    Calls the external Ollama API endpoint (assumed to be GET /api/models) to get a list of models,
    then manually maps each returned model to an OllamaModel instance by assigning the fields one by one.
    
    Returns:
        OllamaModelList: A list of models.
    
    Raises:
        HTTPException: If the request to the Ollama API fails.
    """
    url = f"{app.config.OLLAMA_URL}/api/tags"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url)
            response.raise_for_status()

    except httpx.HTTPError as exc:
        logger.error(f"Error fetching model list: {exc}")

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error fetching models: {exc}"
        )

    result = response.json()
    models_raw = result.get("models") or result.get("data") or result
    models: List[OllamaModel] = []

    for item in models_raw:
        try:
            name = item.get("name") or "unknown"
            modified_at = item.get("modified_at", "")

            details = item.get("details", {})
            parameter_size = details.get("parameter_size", "")
            quantization_level = details.get("quantization_level", "")
            context_length = 0

            model_obj = OllamaModel(
                name=name,
                modified_at=modified_at,
                parameter_size=parameter_size,
                quantization_level=quantization_level,
                context_length=context_length
            )

            models.append(model_obj)

        except Exception as e:
            logger.error(f"Error mapping model item: {e}")
            continue

    return OllamaModelList(data=models)


@router.get("/api/models/{model_name}", response_model=OllamaModel)
async def get_model(model_name: str) -> OllamaModel:
    """
    Retrieves detailed information for a specific model from the Ollama API.
    
    This endpoint sends a POST request to Ollama's /api/show endpoint with a payload 
    of {"model": model_name} (since Ollama expects a POST for model info) rather than a GET.
    
    The returned JSON is then manually mapped to an OllamaModel instance by assigning each field one by one.
    
    Args:
        model_name (str): The name of the model to retrieve.
    
    Returns:
        OllamaModel: Detailed model information.
    
    Raises:
        HTTPException: If the request to Ollama's API fails or the response format is invalid.
    """
    url = f"{app.config.OLLAMA_URL}/api/show"
    payload = {"model": model_name}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

    except httpx.HTTPError as exc:
        logger.error(f"Error fetching model '{model_name}': {exc}")

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error fetching model '{model_name}': {exc}"
        )

    data = response.json()

    try:
        modified_at = data.get("modified_at", "")

        details = data.get("details", {})

        parameter_size = details.get("parameter_size", "")

        quantization_level = details.get("quantization_level", "")

        model_info = data.get("model_info", {})

        context_length = model_info.get("llama.context_length")
        if context_length is None:
            context_length = 0

        model_obj = OllamaModel(
            name=model_name,
            modified_at=modified_at,
            parameter_size=parameter_size,
            quantization_level=quantization_level,
            context_length=context_length
        )
    except Exception as e:
        logger.error(f"Error mapping model '{model_name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing model '{model_name}': {e}."
        )

    return model_obj