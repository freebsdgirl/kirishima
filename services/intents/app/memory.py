"""
This module provides functionality for processing memory-related operations 
within a `ProxyMessage`. It identifies and handles specific function calls 
(create_memory and delete_memory) embedded in the message content, logs 
debug information about these operations, and modifies the message content 
by removing the identified function calls while preserving other text.
Functions:
    process_memory(message: ProxyMessage, component: str) -> ProxyMessage:
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
import httpx
from shared.models.chromadb import MemoryEntry
from shared.consul import get_service_address


async def process_memory(message: ProxyMessage, component: str) -> ProxyMessage:
    """
    Process memory-related operations within a ProxyMessage.
    
    Extracts and handles create_memory() and delete_memory() function calls from message content.
    Removes these function calls from the message while preserving other text.
    Logs debug information about detected memory operations.
    
    Args:
        message (ProxyMessage): The input message to process.
        component (str): The component string from the intent request.
    
    Returns:
        ProxyMessage: The modified message with memory function calls removed.
    
    Raises:
        HTTPException: If an unexpected error occurs during memory processing.
    """
    try:
        # --- Remove code block markers (triple backticks and optional language) around memory calls ---
        codeblock_pattern = re.compile(
            r'```(?:[a-zA-Z0-9_+-]*)?\n?((?:.|\n)*?)```',
            re.MULTILINE
        )
        def strip_codeblock(match):
            inner = match.group(1)
            if re.search(r'(create_memory\(|delete_memory\()', inner):
                return inner.strip()  # Remove code block, keep content
            return match.group(0)  # Leave other code blocks untouched
        original_content = codeblock_pattern.sub(strip_codeblock, message.content)

        # --- Run memory HTTP requests on the original content (before replacement) ---
        create_memory_pattern = re.compile(
            r'create_memory\(\s*["\'“”]?(.+?)["\'“”]?\s*,\s*([0-9]*\.?[0-9]+)\s*\)',
            re.IGNORECASE
        )
        for text, priority in create_memory_pattern.findall(original_content):
            clean_text = text.strip('"\'“”').strip()
            logger.debug(f"🗃️ function: create_memory({clean_text}, {priority})")
            if not component:
                logger.error("Component is required for memory creation but was None or empty.")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Component is required for memory creation."
                )
            try:
                brain_address, brain_port = get_service_address('brain')
                entry = MemoryEntry(memory=clean_text, component=component, priority=float(priority), mode="default")
                entry_dict = entry.model_dump(exclude_none=True)
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(f"http://{brain_address}:{brain_port}/memory", json=entry_dict)
                    response.raise_for_status()
            except Exception as e:
                logger.error(f"Error creating memory in brain: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error creating memory in brain: {e}"
                )

        delete_memory_pattern = re.compile(
            r'delete_memory\(\s*["\'“”]?(.+?)["\'“”]?\s*\)',
            re.IGNORECASE
        )
        for text in delete_memory_pattern.findall(original_content):
            clean_text = text.strip('"\'“”').strip()
            logger.debug(f"🗃️ function: delete_memory({clean_text})")
            try:
                brain_address, brain_port = get_service_address('brain')
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.get(f"http://{brain_address}:{brain_port}/mode")
                    response.raise_for_status()
                    json_response = response.json()
                    mode = json_response.get("message", None)
                entry = MemoryEntry(memory=clean_text, component=component, mode=mode, embedding=[])
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.request(
                        method="DELETE",
                        url=f"http://{brain_address}:{brain_port}/memory",
                        json=entry.model_dump()
                    )
                    if response.status_code == 404:
                        message._deleted_memory_id = None
                    elif response.status_code in (200, 204):
                        # Extract deleted memory id from response if available
                        deleted_id = None
                        try:
                            deleted_id = response.json().get("id")
                        except Exception:
                            pass
                        message._deleted_memory_id = deleted_id
                    else:
                        logger.error(f"Failed to delete memory: {response.status_code} {response.text}")
                        message._deleted_memory_id = None
            except Exception as e:
                logger.error(f"Error deleting memory in brain: {e}")
                message._deleted_memory_id = None

        # --- Replace memory function calls with HTML details/summary blocks in the cleaned content ---
        def create_memory_repl(match):
            text = match.group(1)
            priority = match.group(2)
            clean_text = text.strip('"\'“”').strip()
            return f"<details>\n<summary>Memory Created</summary>\n> {clean_text}, {priority}\n</details>"

        def delete_memory_repl(match):
            text = match.group(3)
            clean_text = text.strip('"\'“”').strip()
            deleted_id = getattr(message, '_deleted_memory_id', None)
            if deleted_id:
                return f"<details>\n<summary>Memory Deleted</summary>\n> {deleted_id}\n</details>"
            else:
                return f"<details>\n<summary>Memory Deletion Failed.</summary>\n> Memory not found: {clean_text}\n</details>"

        combined_sub_pattern = re.compile(
            r'create_memory\(\s*["\'“”]?(.+?)["\'“”]?\s*,\s*([0-9]*\.?[0-9]+)\s*\)'
            r'|delete_memory\(\s*["\'“”]?(.+?)["\'“”]?\s*\)',
            re.IGNORECASE
        )
        def memory_replacer(match):
            if match.group(1) is not None and match.group(2) is not None:
                return create_memory_repl(match)
            elif match.group(3) is not None:
                return delete_memory_repl(match)
            return ''
        message.content = combined_sub_pattern.sub(memory_replacer, original_content)

    except Exception as e:
        logger.error(f"Unexpected error in memory processing: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error in memory processing: {e}"
        )

    return message