"""
Utility functions for sending notifications via Discord and iMessage, and retrieving user contact information.
This module provides asynchronous helper functions to:
- Send direct messages to users via Discord (`_send_discord_dm`)
- Send direct messages to users via iMessage (`_send_imessage`)
- Retrieve user contact information from the contacts service (`_get_contact`)
- Retrieve and format recent summaries from chromadb (`get_recent_summaries`)
All services are discovered via Consul and accessed using HTTP requests. Errors are logged and appropriate exceptions are raised for HTTP and general failures.
"""

from shared.models.contacts import Contact
from shared.models.imessage import OutgoingiMessage
from shared.models.discord import SendDMRequest
from shared.models.summary import Summary

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx
import json
import os

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


async def _send_discord_dm(user_id: str, message: str):
    """
    Send a direct message to a user via Discord.
    
    This function attempts to send a notification to a specified user through the Discord service.
    It constructs a SendDMRequest with the user ID and message, connects to the Discord service
    via Consul, and sends the message using an HTTP POST request.
    
    Args:
        user_id (str): The unique identifier of the user to receive the Discord DM.
        message (str): The content of the message to be sent.
    
    Raises:
        HTTPStatusError: If the Discord service returns a non-successful HTTP status.
        HTTPException: If there is a general error in sending the Discord notification.
    """
    try:
        dm = SendDMRequest(
            user_id=user_id,
            content=message
        )

        discord_port = os.getenv("DISCORD_PORT", 4209)
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(f"http://discord:{discord_port}/dm", json=dm.model_dump())
            response.raise_for_status()
            logger.info(f"✅ Notification sent to {user_id} via Discord")

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error from Discord: {e.response.status_code} - {e.response.text}")
        raise

    except Exception as e:
        logger.error(f"Failed to contact Discord: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send notification via Discord: {e}"
        )


async def _send_imessage(user_id: str, message: str):
    """
    Send a direct message to a user via iMessage.
        
    This function attempts to send a notification to a specified user through the iMessage service.
    It constructs an OutgoingiMessage with the user ID and message, connects to the iMessage service
    via Consul, and sends the message using an HTTP POST request.
        
    Args:
        user_id (str): The unique identifier of the user to receive the iMessage.
        message (str): The content of the message to be sent.
        
    Raises:
        HTTPStatusError: If the iMessage service returns a non-successful HTTP status.
        HTTPException: If there is a general error in sending the iMessage notification.
    """
    try:

        imessage_port = os.getenv("IMESSAGE_PORT", 4204)
        imessage = OutgoingiMessage(
            address=user_id,
            message=message
        )
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(f"http://imessage:{imessage_port}/imessage/send", json=imessage.model_dump())
            response.raise_for_status()
            logger.info(f"✅ Notification sent to {user_id} via iMessage")

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error from iMessage: {e.response.status_code} - {e.response.text}")
        raise

    except Exception as e:
        logger.error(f"Failed to contact iMessage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send notification via iMessage: {e}"
        )


async def _get_contact(user_id: str) -> Contact:
    """
    Retrieve the contact information for a user.
    
    This function attempts to get the contact information for a specified user from the contacts service.
    It connects to the contacts service via Consul and retrieves the contact information using an HTTP GET request.
    
    Args:
        user_id (str): The unique identifier of the user whose contact information is to be retrieved.
    
    Returns:
        Contact: The contact information of the user.
    
    Raises:
        HTTPStatusError: If the contacts service returns a non-successful HTTP status.
        HTTPException: If there is a general error in retrieving the contact information.
    """
    try:
        contacts_port = os.getenv("CONTACTS_PORT", 4202)
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"http://contacts:{contacts_port}/contact/{user_id}")
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        if e.response.status_code == status.HTTP_404_NOT_FOUND:
            logger.info(f"No contact found for {user_id}, skipping.")
            return None
        else:
            logger.error(f"HTTP error from contacts: {e.response.status_code} - {e.response.text}")
            raise

    except Exception as e:
        logger.error(f"Failed to contact contacts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve contact: {e}"
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
        endpoint = f"/ledger/user/{user_id}/sync"
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
