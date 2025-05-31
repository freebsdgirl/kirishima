"""
This module provides functionality for processing mode-related requests.
Functions:
    process_mode(message: ProxyMessage) -> int:
        Processes mode-related commands extracted from the message content.
        It identifies mode commands using a regular expression, logs the 
        extracted arguments, and sends a request to the "brain" service to 
        update the mode. Raises HTTPException on errors.
Dependencies:
    - fastapi: For HTTPException and status codes.
    - shared.models.proxy.ProxyMessage: For the message object structure.
    - re: For regular expression operations.
    - httpx: For making asynchronous HTTP requests.
    - shared.consul.get_service_address: For retrieving service addresses.
    - shared.log_config.get_logger: For logging operations.
"""
from app.modes import mode_set

from shared.models.proxy import ChatMessage

from shared.consul import get_service_address

from shared.log_config import get_logger
logger = get_logger(f"intents.{__name__}")

import re
import json

from fastapi import HTTPException, status

with open('/app/shared/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


def process_mode(message: ChatMessage) -> ChatMessage:
    """
    Processes mode-related commands extracted from a ChatMessage.
    
    Extracts mode commands using a regex pattern, logs the arguments, and sends 
    a request to the brain service to update the mode. Handles potential errors 
    with appropriate HTTP exceptions.
    
    Args:
        message (ChatMessage): The message containing mode command content.
    
    Returns:
        int: HTTP 200 OK status code if mode processing is successful.
    
    Raises:
        HTTPException: If there are errors in mode processing or service communication.
    """
    try:
        mode_pattern = re.compile(
            r'mode\(\s*[\'"]?(.+?)[\'"]?\s*\)',
            re.IGNORECASE
        )

        for match in mode_pattern.findall(message.content):
            logger.debug(f"🗃️ function: mode({match})")
            
            # do the thing to change the mode
            mode_set(match)

    except Exception as e:
        logger.error(f"Unexpected error in mode processing: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error in mode processing: {e}"
        )
    
    return message
