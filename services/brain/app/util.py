"""
Utility functions for interacting with external services such as contacts, chromadb, and ledger,
as well as message sanitization helpers.
This module provides asynchronous helpers for:
- Retrieving admin user IDs and user aliases from the contacts service.
- Sanitizing message content by removing HTML details tags.
- Posting data to other services using Consul service discovery.
- Fetching and formatting recent user summaries from chromadb.
- Synchronizing message snapshots with the ledger service.
Logging is performed for error handling and debugging. HTTPException is raised for
service communication errors to be handled by FastAPI endpoints.
"""

from shared.models.contacts import Contact
from shared.models.summary import Summary

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx
import re
import json
import os

from fastapi import HTTPException, status

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


async def get_admin_user_id() -> str:
    """
    Retrieve the user ID for the admin user from the contacts service.
    
    Queries the contacts service to find a user with the '@ADMIN' tag and returns their user ID.
    Raises an HTTPException if there are any HTTP-related errors during the retrieval process.
    
    Returns:
        str: The unique identifier of the admin user.
    
    Raises:
        ValueError: If no admin user is found in the contacts service.
        HTTPException: If there is an error communicating with the contacts service.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            contacts_port = os.getenv("CONTACTS_PORT", 4202)
            contact_response = await client.get(
                f"http://contacts:{contacts_port}/search",
                params={"q": "@ADMIN"}
            )
            
            contact_response.raise_for_status()
            data = contact_response.json()
            if not data.get("id"):
                logger.error("No admin user found in contacts service.")
                raise ValueError("No admin user found in contacts service.")
            return data["id"]

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail="Error retrieving admin user ID."
            )
        
        except Exception as e:
            logger.exception("Error retrieving admin user ID from contacts service:", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while retrieving admin user ID."
            )


async def get_user_alias(user_id: str) -> str:
    """
    Retrieve the alias for a specific user from the contacts service.
    
    Queries the contacts service to find a user with the specified user ID and returns their alias.
    Raises an HTTPException if there are any HTTP-related errors during the retrieval process.
    
    Args:
        user_id (str): The unique identifier of the user whose alias is to be retrieved.
    
    Returns:
        str: The alias of the specified user.
    
    Raises:
        HTTPException: If there is an error communicating with the contacts service.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            contacts_port = os.getenv("CONTACTS_PORT", 4202)
            contact_response = await client.get(f"http://contacts:{contacts_port}/contact/{user_id}")
            contact_response.raise_for_status()

            model = Contact.model_validate(contact_response.json())
            if not model.aliases or not isinstance(model.aliases, list) or not model.aliases[0]:
                logger.error(f"No alias found for user {user_id} in contacts service.")
                raise ValueError(f"No alias found for user {user_id} in contacts service.")

            return model.aliases[0]

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail="Error retrieving user alias."
            )
        
        except Exception as e:
            logger.exception("Error retrieving user alias from contacts service:", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while retrieving user alias."
            )


def sanitize_messages(messages):
    """
    Sanitizes a list of messages by removing HTML details tags and stripping whitespace.
    
    Args:
        messages (list): A list of message dictionaries to sanitize.
    
    Returns:
        list: The sanitized list of messages with details tags removed and whitespace stripped.
    
    Logs an error for any non-dictionary messages encountered during processing.
    """
    for message in messages:
        if isinstance(message, dict):
            content = message.get('content', '')
            content = re.sub(r'<details>.*?</details>', '', content, flags=re.DOTALL)
            content = content.strip()
            message['content'] = content
        else:
            logger.error(f"Expected message to be a dict, but got {type(message)}")
    return messages


async def post_to_service(service_name, endpoint, payload, error_prefix, timeout=60):
    """
    Sends a POST request to a specified service endpoint using Consul service discovery.
    
    Args:
        service_name (str): Name of the target service.
        endpoint (str): API endpoint path to call.
        payload (dict): JSON payload to send with the request.
        error_prefix (str): Prefix for error logging and exception messages.
        timeout (int, optional): Request timeout in seconds. Defaults to 60.
    
    Returns:
        httpx.Response: The response from the service.
    
    Raises:
        HTTPException: If service is unavailable, connection fails, or HTTP error occurs.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        service_env = service_name.upper()
        port = os.getenv(f"{service_env}_PORT")

        try:
            response = await client.post(f"http://{service_name}:{port}{endpoint}", json=payload)
            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from {service_name} service: {http_err.response.status_code} - {http_err.response.text}")
            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"{error_prefix}: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error forwarding to {service_name} service: {req_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error to {service_name} service: {req_err}"
            )

        except Exception as e:
            logger.error(f"Unexpected error while posting to {service_name} service: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred while posting to {service_name} service."
            )


async def get_recent_summaries(user_id: str, limit: int = 4) -> str:
    """
    Retrieve and format the most recent summaries for a user from chromadb.
    Returns a string suitable for prompt injection.
    Raises HTTPException if no summaries are found or on error.
    """

    try:
        chromadb_port = os.getenv("CHROMADB_PORT", 4206)
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"http://chromadb:{chromadb_port}/summary?user_id={user_id}&limit={limit}")
            response.raise_for_status()
            summaries_list = response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == status.HTTP_404_NOT_FOUND:
            logger.info(f"No summaries found for {user_id}, skipping.")
            summaries_list = []
        else:
            logger.error(f"HTTP error from chromadb: {e.response.status_code} - {e.response.text}")
            raise
    except Exception as e:
        logger.error(f"Failed to contact chromadb to get a list of summaries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve summaries: {e}")
    if not summaries_list:
        logger.warning("No summaries found for the specified period.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No summaries found for the specified period."
        )
    summary_lines = []
    for s in summaries_list:
        summary = Summary.model_validate(s) if not isinstance(s, Summary) else s
        meta = summary.metadata
        if meta is not None:
            if meta.summary_type.value == "daily":
                date_str = meta.timestamp_begin.split(" ")[0]
                label = date_str
            else:
                label = meta.summary_type.value
        else:
            label = "summary"
        summary_lines.append(f"[{label}] {summary.content}")
    return "\n".join(summary_lines)


async def sync_with_ledger(
    user_id: str,
    platform: str,
    snapshot: list,
    error_prefix: str = "Error forwarding to ledger service",
    drop_before_first_user: bool = True,
    endpoint: str = None,
    post_to_service_func=None,
    logger=None
):
    """
    Helper to sync a message snapshot with the ledger service and return the processed buffer.
    - user_id: user id for the ledger endpoint
    - platform: platform string
    - snapshot: list of message dicts
    - error_prefix: error prefix for logging
    - drop_before_first_user: if True, drop all messages before the first user message
    - endpoint: override the ledger endpoint (default: /ledger/user/{user_id}/sync)
    - post_to_service_func: function to use for posting (for testability)
    - logger: logger instance
    Returns: processed ledger buffer (list of dicts)
    """
    if post_to_service_func is None:
        from app.util import post_to_service
        post_to_service_func = post_to_service
    if logger is None:
        from shared.log_config import get_logger
        logger = get_logger("brain.util")
    if endpoint is None:
        endpoint = f"/user/{user_id}/sync"
    try:
        ledger_response = await post_to_service_func(
            'ledger',
            endpoint,
            {"snapshot": snapshot},
            error_prefix=error_prefix
        )
        ledger_buffer = ledger_response.json()
        if drop_before_first_user:
            for i, m in enumerate(ledger_buffer):
                if m.get("role") == "user":
                    if i > 0:
                        logger.warning(f"Ledger buffer did not start with user message, dropping {i} messages before first user message (roles: {[m2.get('role') for m2 in ledger_buffer[:i]]})")
                    return ledger_buffer[i:]
            logger.warning("Ledger buffer contains no user message; returning empty message list.")
            return []
        return ledger_buffer
    except Exception as e:
        logger.error(f"Error sending messages to ledger sync endpoint: {e}")
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync messages with ledger service."
        )
