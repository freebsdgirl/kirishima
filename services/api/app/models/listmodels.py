"""
This module defines API endpoints for listing available language models in an OpenAI-compatible format.
Endpoints:
    - GET /models: Redirects legacy clients to the versioned '/v1/models' endpoint.
    - GET /v1/models: Returns a list of available models based on the configuration in 'config.json'.
The '/v1/models' endpoint reads model modes from the configuration file, constructs a list of models with their IDs,
creation timestamps, and ownership information, and returns them in a format compatible with OpenAI's API.
Logging is used to record errors and debug information related to the model listing process.
"""

from shared.models.models import OpenAIModelList

from shared.log_config import get_logger
logger = get_logger(f"api.{__name__}")

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
    List available models based on modes in config.json, using mode names as model ids.
    Returns:
        OpenAIModelList: A list of models in OpenAI-compatible format.
    """
    import json
    from datetime import datetime
    
    try:
        with open('/app/config/config.json', 'r') as f:
            config = json.load(f)
    except Exception as e:
        logger.error(f"Could not read config.json: {e}")
        raise HTTPException(status_code=500, detail=f"Could not read config.json: {e}")

    modes = config.get('llm', {}).get('mode', {})
    now = int(datetime.now().timestamp())
    models = []
    for mode, details in modes.items():
        provider = details.get('provider', 'openai')
        owned_by = "Randi-Lee-Harper" if provider == "ollama" else "OpenAI"
        models.append({
            "id": mode,
            "created": now,
            "owned_by": owned_by
        })
    openai_model_list = OpenAIModelList(data=models)
    logger.debug(f"/models Returns:\n{openai_model_list.model_dump_json(indent=4)}")
    return openai_model_list
