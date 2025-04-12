"""
This module defines an API endpoint for listing models in an OpenAI-style format.

Modules and Imports:
- `app.config`: Application-specific configuration.
- `shared.models.models`: Contains the `OllamaModelList` and `OpenAIModelList` models.
- `shared.log_config`: Provides a logger for logging messages.
- `httpx`: Used for making asynchronous HTTP requests.
- `fastapi`: Provides the `APIRouter`, `HTTPException`, and `status` utilities for API routing and error handling.

Endpoint:
- `/v1/models`: A GET endpoint that lists available models in an OpenAI-style format.

1. Makes an HTTP GET request to the brain service at `http://brain:4207/models`.
2. Parses the response as an `OllamaModelList` JSON object.
3. Converts each `OllamaModel` into an `OpenAIModel` using a defined conversion method.
4. Returns an `OpenAIModelList` containing the converted models.

Error Handling:
- Raises an `HTTPException` with a 500 status code if:
    - The HTTP request to the brain service fails.
    - The response from the brain service cannot be parsed.

Logging:
- Logs debug messages for incoming requests.
- Logs errors for failed HTTP requests or response parsing issues.
"""

import app.config

from shared.models.models import OllamaModelList, OpenAIModelList

from shared.consul import get_service_address

from shared.log_config import get_logger
logger = get_logger(f"api.{__name__}")

import httpx

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse
router = APIRouter()


@router.get("/models")
async def openai_completions() -> RedirectResponse:
    """
    Redirect legacy '/models' endpoint to the OpenAI-compatible '/v1/models' endpoint.

    Returns a temporary redirect to ensure backward compatibility with older API clients
    while maintaining the current versioned endpoint structure.

    Returns:
        RedirectResponse: A 307 Temporary Redirect to the '/v1/models' endpoint.
    """
    return RedirectResponse(
        url="/v1/models",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )


@router.get("/v1/models", response_model=OpenAIModelList)
async def list_models():
    """
    List available models from the brain service in OpenAI-compatible format.

    Fetches models from the brain service, converts Ollama model format to OpenAI model format,
    and returns a list of available models.

    Returns:
        OpenAIModelList: A list of models in OpenAI-compatible format.

    Raises:
        HTTPException: If there are errors fetching or parsing models from the brain service.
    """
    logger.debug(f"Received list models request")

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            brain_address, brain_port = get_service_address('brain')

            response = await client.get(f"http://{brain_address}:{brain_port}/models")
            response.raise_for_status()

        except Exception as exc:
            logger.error(f"Error fetching models from brain: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching models from brain: {exc}")

    try:
        ollama_models = OllamaModelList.model_validate_json(response.text)

    except Exception as exc:
        logger.error(f"Failed to parse Ollama models: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to parse Ollama models: {exc}")

    # Convert each OllamaModel to an OpenAIModel
    openai_models = [model.to_openai_model() for model in ollama_models.data]
    openai_model_list = OpenAIModelList(data=openai_models)

    return openai_model_list
