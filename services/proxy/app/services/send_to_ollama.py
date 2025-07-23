import app.config
from shared.models.proxy import OllamaRequest, OllamaResponse

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

import httpx
import json

from fastapi import HTTPException, status

async def send_to_ollama(request: OllamaRequest) -> OllamaResponse:
    """
    Send a payload to the Ollama API for generation.
    
    Sends an asynchronous HTTP POST request to the Ollama API's generate endpoint with the provided payload.
    Handles potential HTTP and request errors, logging details and raising appropriate HTTPExceptions.
    
    Args:
        payload (dict): The payload to send to the Ollama API for generation.
    
    Returns:
        httpx.Response: The response from the Ollama API containing the generated content.
    
    Raises:
        HTTPException: If there are HTTP status errors or connection issues with the Ollama API.
    """
    logger.debug(f"🦙 Request to Ollama API:\n{json.dumps(request.model_dump(), indent=4, ensure_ascii=False)}")

    with open('/app/config/config.json') as f:
        _config = json.load(f)

    TIMEOUT = _config["timeout"]

    payload = {
        "model": request.model,
        "prompt": request.prompt,
        **(request.options or {}),
        "stream": False,
        "raw": True
    }

    if request.format:
        payload['format'] = request.format

    # Send the POST request using an async HTTP client
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.post(f"{app.config.OLLAMA_URL}/api/generate", json=payload)
            response.raise_for_status()

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from Ollama API: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from language model service: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error connecting to Ollama API: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {e}"
            )

    json_response = response.json()
    logger.debug(f"🦙 Response from Ollama API:\n{json.dumps(json_response, indent=4, ensure_ascii=False)}")

    json_response['response'] = json_response['response'].strip()

    ollama_response = OllamaResponse(**json_response)

    return ollama_response