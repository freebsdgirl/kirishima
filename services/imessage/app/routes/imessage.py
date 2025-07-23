"""
FastAPI routes for iMessage service endpoints.

This module contains the route handlers for sending and receiving iMessages
via the BlueBubbles server integration.
"""

from fastapi import APIRouter, Request
from shared.models.imessage import OutgoingiMessage
from app.services.send import send_message
from app.services.recv import receive_webhook

router = APIRouter()


@router.post("/send")
def send_imessage(payload: OutgoingiMessage):
    """
    Send an iMessage to a specified recipient via BlueBubbles server.

    Args:
        payload (OutgoingMessage): Contains the recipient's address and message content.

    Returns:
        dict: A response indicating the message was sent, including the server's response.

    Raises:
        HTTPException: If the message sending process fails, with a 500 status code.
    """
    # Import here to avoid circular dependency
    from app.app import bb_client
    
    return send_message(payload, bb_client)


@router.post("/recv")
async def receive_webhook_endpoint(request: Request):
    """
    Receive and process incoming iMessage webhook from BlueBubbles server.

    This endpoint handles incoming webhook payloads, filters out self-authored messages,
    and forwards new messages to the Brain service for processing.

    Args:
        request (Request): The incoming HTTP request containing the webhook payload.

    Returns:
        dict: A status response indicating whether the message was processed or ignored.

    Raises:
        HTTPException: If payload processing fails or is invalid.
    """
    # Import here to avoid circular dependency
    from app.app import bb_client, TIMEOUT
    
    return await receive_webhook(request, bb_client, TIMEOUT)
