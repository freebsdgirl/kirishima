"""
This module provides functionality for processing memory-related operations 
within a `ProxyMessage`. It identifies and handles specific function calls 
(create_memory and delete_memory) embedded in the message content, logs 
debug information about these operations, and modifies the message content 
by removing the identified function calls while preserving other text.
Functions:
    process_memory(message: ProxyMessage) -> ProxyMessage:
        Processes memory-related operations in a ProxyMessage, extracts 
        create_memory() and delete_memory() function calls, logs debug 
        information, and modifies the message content by removing these 
        function calls.
Dependencies:
    - fastapi.HTTPException: For raising HTTP exceptions in case of errors.
    - fastapi.status: For HTTP status codes.
    - shared.models.proxy.ProxyMessage: The ProxyMessage model.
    - shared.log_config.get_logger: For logging debug information.
    - re: For regular expression operations.
"""

from fastapi import HTTPException, status
from shared.models.proxy import ProxyMessage

from shared.log_config import get_logger
logger = get_logger(f"intents.{__name__}")

import re


async def process_memory(message: ProxyMessage) -> ProxyMessage:
    """
    Process memory-related operations within a ProxyMessage.
    
    Extracts and handles create_memory() and delete_memory() function calls from message content.
    Removes these function calls from the message while preserving other text.
    Logs debug information about detected memory operations.
    
    Args:
        message (ProxyMessage): The input message to process.
    
    Returns:
        ProxyMessage: The modified message with memory function calls removed.
    
    Raises:
        HTTPException: If an unexpected error occurs during memory processing.
    """
    try:
        create_memory_pattern = re.compile(
            r'create_memory\(\s*[\'"]?(.+?)[\'"]?\s*,\s*([0-9]*\.?[0-9]+)\s*\)',
            re.IGNORECASE
        )

        for text, priority in create_memory_pattern.findall(message.content):
            logger.debug(f"🗃️ function: create_memory({text}, {priority})")
            
            # placeholder until brain endpoints are ready.
    
        delete_memory_pattern = re.compile(
            r'delete_memory\(\s*[\'"]?(.+?)[\'"]?\s*\)',
            re.IGNORECASE
        )

        for text in delete_memory_pattern.findall(message.content):
            logger.debug(f"🗃️ function: delete_memory({text})")
            
            # placeholder until brain endpoints are ready.

        # Combine both patterns into a single regex
        combined_pattern = re.compile(
            f"{create_memory_pattern.pattern}|{delete_memory_pattern.pattern}",
            re.IGNORECASE
        )

        # Check if the message content only contains the pattern
        if combined_pattern.fullmatch(message.content.strip()):
            return message  # Return the message as-is if it only contains the pattern

        # Remove the pattern and any preceding newline if other text exists
        modified_content = combined_pattern.sub('', message.content).lstrip('\n')
        message.content = modified_content

    except Exception as e:
        logger.error(f"Unexpected error in memory processing: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error in memory processing: {e}"
        )

    return message