"""
Utility functions for sending notifications via Discord and iMessage, and retrieving user contact information.
This module provides asynchronous helper functions to:
- Send direct messages to users via Discord (`_send_discord_dm`)
- Send direct messages to users via iMessage (`_send_imessage`)
- Retrieve user contact information from the contacts service (`_get_contact`)
All services are discovered via Consul and accessed using HTTP requests. Errors are logged and appropriate exceptions are raised for HTTP and general failures.
"""
from shared.config import TIMEOUT

from shared.models.contacts import Contact
from shared.models.imessage import OutgoingiMessage
from shared.models.discord import SendDMRequest

import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


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

        discord_address, discord_port = shared.consul.get_service_address('discord')
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(f"http://{discord_address}:{discord_port}/dm", json=dm.model_dump())
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
        imessage_address, imessage_port = shared.consul.get_service_address('imessage')
        imessage = OutgoingiMessage(
            address=user_id,
            message=message
        )
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(f"http://{imessage_address}:{imessage_port}/imessage/send", json=imessage.model_dump())
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
        contacts_address, contacts_port = shared.consul.get_service_address('contacts')
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"http://{contacts_address}:{contacts_port}/contact/{user_id}")
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
