import httpx

from shared.models.smarthome import UserRequest
from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import json
import os

async def smarthome(user_request: str, device: str = None) -> str:
    """
    Sends a user request to the smarthome service via Consul service discovery.
    
    Args:
        user_request (str): The full text request from the user.
        device (str, optional): The name of the specific device, if applicable.
    
    Returns:
        str: JSON-encoded response from the smarthome service, or an error message.
    
    Raises:
        Handles httpx.TimeoutException and httpx.RequestError, logging errors and returning
        JSON-encoded error responses.
    """
    if not user_request:
        return json.dumps({"error": "User request cannot be empty."})

    data = UserRequest(full_request=user_request, name=device)
    try:
        smarthome_port = os.getenv("SMARTHOME_PORT", 4211)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f'http://smarthome:{smarthome_port}/user_request',
                json=data.model_dump()
            )
            response.raise_for_status()
            data = response.json()
            return data
    except httpx.TimeoutException:
        logger.error("Request timed out.")
        return json.dumps({"error": "Request timed out."})
    except httpx.RequestError as e:
        logger.error(f"An error occurred: {e}")
        return json.dumps({"error": str(e)})