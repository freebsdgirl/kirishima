"""
This module defines an API endpoint for single-turn text completion using the FastAPI framework.

Functions:
    single_turn_completion(request_data: dict):
        Handles POST requests to the "/completions" endpoint. It processes a single-turn prompt
        and sends it to the Ollama API for text completion. The response is then converted to
        OpenAI's format and returned to the client.

        Args:
            request_data (dict): A dictionary containing the input data for the completion request.
                - "prompt" (str): The input text prompt for the completion. This field is required.
                - "temperature" (float, optional): Sampling temperature for the completion.
                - "top_p" (float, optional): Nucleus sampling parameter.
                - "max_tokens" (int, optional): Maximum number of tokens to generate.
        
        Returns:
            dict: A dictionary in OpenAI's text completion format containing the generated text
            and metadata.

        Raises:
            HTTPException: If the prompt is missing, or if there is an error in the request to
            the Ollama API, or if any other exception occurs during processing.
"""
from app.config import DEFAULT_SETTINGS, OLLAMA_API_URL

from shared.log_config import get_logger
logger = get_logger(__name__)

import requests

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/completions")
async def single_turn_completion(request_data: dict):
    """
    Handle single-turn text completion requests via Ollama API.

    Processes a text prompt, sends it to Ollama, and returns the response in OpenAI-compatible format.
    Supports optional parameters like temperature, top_p, and max_tokens.

    Args:
        request_data (dict): Completion request parameters including prompt and optional settings.

    Returns:
        dict: Text completion response in OpenAI format with generated text and metadata.

    Raises:
        HTTPException: For invalid requests, API errors, or processing failures.
    """
    try:
        prompt = request_data.get("prompt", "").strip()

        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prompt is required."
            )

        logger.debug(f"🔹 Single-turn completion requested: {prompt}")

        # Construct payload for ollama
        payload = {
            "model": DEFAULT_SETTINGS["model"],
            "prompt": prompt,  # Single-turn prompt (no chat history)
            "stream": DEFAULT_SETTINGS["stream"],
            "options": {
                "temperature": request_data.get("temperature", DEFAULT_SETTINGS["temperature"]),
                "top_p": request_data.get("top_p", DEFAULT_SETTINGS["top_p"]),
                "max_tokens": request_data.get("max_tokens", DEFAULT_SETTINGS["max_tokens"]),
                "stop": DEFAULT_SETTINGS["stop"]
            }
        }

        # Send request to ollama
        response = requests.post(OLLAMA_API_URL, json=payload)

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )

        ollama_response = response.json()

        # Convert ollama response back to OpenAI format
        openai_response = {
            "id": "textcmpl-ollama",
            "object": "text_completion",
            "created": ollama_response.get("created", 0),
            "model": DEFAULT_SETTINGS["model"],
            "choices": [
                {
                    "index": 0,
                    "text": ollama_response.get("response", "").strip(),
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }

        logger.debug(f"🔹 Single-turn completion output: {openai_response}")

        return openai_response

    except Exception as e:
        logger.error(f"❌ ERROR: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
