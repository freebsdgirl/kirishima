"""
This module provides FastAPI endpoints for handling model-related operations, including
redirecting requests for OpenAI model compatibility and retrieving model details in
OpenAI-compatible format.
The endpoints interact with a backend service ("brain") to fetch model data and transform
it into the desired format. The module also includes error handling for issues such as
network failures or invalid data.
Classes:
    None
Functions:
    openai_completions(model_id: str) -> RedirectResponse:
        Redirects POST requests to the v1 models endpoint with a temporary redirect status code.
    get_model(model_id: str) -> OpenAIModel:
        Retrieves a specific model by its ID, validates the data, and converts it to an
        OpenAI-compatible format.
Dependencies:
    - app.config: Application configuration.
    - shared.models.models: Contains the OpenAIModel and OllamaModel classes.
    - shared.log_config: Provides logging functionality.
    - httpx: For making asynchronous HTTP requests.
    - fastapi: For building the API endpoints.
    - os: For environment variable access.
Environment Variables:
    - BRAIN_HOST: Hostname of the brain service (default: "brain").
    - BRAIN_PORT: Port of the brain service (default: "4207").
    - BRAIN_URL: Full URL of the brain service (default: "http://{BRAIN_HOST}:{BRAIN_PORT}").
"""

import app.config

from shared.models.models import OpenAIModel, OllamaModel

from shared.log_config import get_logger
logger = get_logger(f"api.{__name__}")

import httpx

import os
brain_host = os.getenv("BRAIN_HOST", "brain")
brain_port = os.getenv("BRAIN_PORT", "4207")
brain_url = os.getenv("BRAIN_URL", f"http://{brain_host}:{brain_port}")

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

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.get(f"{brain_url}/model/{model_id}")
            response.raise_for_status()

        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching model from brain: {exc}"
            )
    
    try:
        ollama_model = OllamaModel.model_validate_json(response.text)

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse the returned model data: {exc}"
        )

    # Convert the OllamaModel to an OpenAIModel
    openai_model = ollama_model.to_openai_model()

    return openai_model
