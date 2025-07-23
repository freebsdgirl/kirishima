"""
This module provides functionality to send iMessages using the BlueBubbles client.

Functions:
    send_message(payload: OutgoingiMessage, bb_client: BlueBubblesClient):
        Sends an iMessage to a specified recipient using the provided BlueBubbles client instance.
        Handles HTTP errors and logs the sending process.
"""
from app.services.client import BlueBubblesClient

from shared.models.imessage import OutgoingiMessage

from shared.log_config import get_logger
logger = get_logger(f"imessage.{__name__}")

import httpx
from fastapi import HTTPException


def send_message(payload: OutgoingiMessage, bb_client: BlueBubblesClient):
    """
    Send an iMessage using the BlueBubbles client.

    Args:
        payload (OutgoingiMessage): Contains the recipient's address and message content.
        bb_client (BlueBubblesClient): The BlueBubbles client instance.

    Returns:
        dict: A response indicating the message was sent, including the server's response.

    Raises:
        HTTPException: If the message sending process fails.
    """
    logger.info(f"Sending iMessage to {payload.address}")

    try:
        result = bb_client.send_message(payload.address, payload.message)
        return {
            "status": "sent",
            "response": result
        }

    except httpx.HTTPStatusError as e:
        logger.warning(f"BlueBubbles returned HTTP error: {e.response.status_code}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.text
        )
