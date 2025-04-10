"""
This module defines an API endpoint for retrieving a list of available models 
from the Ollama API.

Modules:
    - fastapi: Provides the APIRouter and HTTPException classes for defining 
      and handling API routes.
    - requests: Used to make HTTP requests to the Ollama API.
    - log_config: Custom module for configuring and retrieving a logger instance.

Constants:
    - OLLAMA_API_URL (str): Base URL for the Ollama API.

Routes:
    - GET /models: Fetches a list of available models from the Ollama API.

Functions:
    - list_models(): Asynchronous function that handles the GET /models route. 
      It retrieves and returns a list of models from the Ollama API. Logs 
      requests and responses for debugging purposes and raises an HTTPException 
      in case of errors.
"""

from fastapi import APIRouter, HTTPException

import requests

from shared.log_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

OLLAMA_API_URL = "http://localhost:11434/api"


@router.get("/models")
async def list_models():
    """
    Retrieve a list of available Ollama models.

    Returns:
        A JSON response containing details of all available models from the Ollama API.

    Raises:
        HTTPException: If there is an error retrieving the models, with a 500 status code.
    """
    try:
        # Log request if debug mode is enabled
        logger.debug("🔹 Model list requested")

        response = requests.get(f"{OLLAMA_API_URL}/tags")
        models_data = response.json()

        # Log response if debug mode is enabled
        logger.debug(f"🔹 Model List Response: {models_data}")

        return models_data


    except Exception as e:
        logger.error(f"❌ ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
