"""
This module defines FastAPI endpoints for retrieving and redirecting OpenAI model information.

Endpoints:
    - GET /models/{model_id}: Redirects to the v1 models endpoint for compatibility.
    - GET /v1/models/{model_id}: Returns model information for the specified mode from config.json.

The endpoints utilize a shared OpenAIModel schema and log configuration. Model details are loaded
from a shared configuration file, and appropriate HTTP exceptions are raised for errors.
"""

from shared.models.models import OpenAIModel

from shared.log_config import get_logger
logger = get_logger(f"api.{__name__}")

import json
from datetime import datetime

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
    Return model info for the requested mode (e.g., nsfw, default, summarize) from config.json.

    Args:
        model_id (str): The mode to look up (e.g., 'nsfw', 'default', 'summarize').

    Returns:
        OpenAIModel: The model info for the requested mode.

    Raises:
        HTTPException: If there's an error fetching or parsing the model data.
    """
    try:
        with open('/app/config/config.json', 'r') as f:
            config = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read config.json: {e}")

    modes = config.get('llm', {}).get('mode', {})
    details = modes.get(model_id)
    if not details:
        raise HTTPException(status_code=404, detail=f"Mode '{model_id}' not found in config.json")

    now = int(datetime.now().timestamp())
    model_name = details.get('model', model_id)
    provider = details.get('provider', 'openai')
    owned_by = "Randi-Lee-Harper" if provider == "ollama" else "OpenAI"
    return OpenAIModel(id=model_name, created=now, owned_by=owned_by)
