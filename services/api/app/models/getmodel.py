"""
This module defines API endpoints for retrieving and redirecting model information in OpenAI-compatible format.
Endpoints:
    - GET /models/{model_id}: Redirects to the v1 models endpoint for compatibility with OpenAI API clients.
    - GET /v1/models/{model_id}: Fetches a model from the brain service, validates and transforms it into an OpenAIModel.
Dependencies:
    - shared.models.models: Contains model schemas for OpenAIModel and OllamaModel.
    - shared.consul: Provides service discovery utilities.
    - shared.config: Contains configuration constants such as TIMEOUT.
    - shared.log_config: Provides logging utilities.
    - httpx: Used for asynchronous HTTP requests.
    - fastapi: Web framework for building API endpoints.
    - HTTPException: If there is an error fetching or parsing model data from the brain service.
"""

from shared.models.models import OpenAIModel, OllamaModel

from shared.consul import get_service_address
from shared.config import TIMEOUT

from shared.log_config import get_logger
logger = get_logger(f"api.{__name__}")

import httpx

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse
router = APIRouter()


@router.get("/models/{model_id}")
async def openai_completions(model_id: str) -> RedirectResponse:
    """
    Redirect endpoint for OpenAI model compatibility.

    Handles POST requests to the models endpoint by redirecting to the corresponding
    v1 models endpoint with a temporary redirect status code.

    Args:
        model_id (str): The unique identifier of the model to retrieve.

    Returns:
        RedirectResponse: A temporary redirect to the v1 models endpoint.
    """
    return RedirectResponse(
        url="/v1/models/{model_id}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )


@router.get("/v1/models/{model_id}", response_model=OpenAIModel)
async def get_model(model_id: str):
    """
    Retrieve a specific model by its ID and convert it from Ollama to OpenAI format.

    Fetches a model from the brain service using the provided model ID, validates the returned
    model data, and transforms it into an OpenAI-compatible model representation.

    Args:
        model_id (str): The unique identifier of the model to retrieve.

    Returns:
        OpenAIModel: The model details in OpenAI format.

    Raises:
        HTTPException: If there's an error fetching or parsing the model data.
    """

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            brain_address, brain_port = get_service_address('brain')
            response = await client.get(f"http://{brain_address}:{brain_port}/model/{model_id}")
            response.raise_for_status()

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching model from brain: {e}"
            )
    
    try:
        ollama_model = OllamaModel.model_validate_json(response.text)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse the returned model data: {e}"
        )

    # Convert the OllamaModel to an OpenAIModel
    openai_model = ollama_model.to_openai_model()

    return openai_model
