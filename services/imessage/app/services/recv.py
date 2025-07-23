"""
Receive webhook service for iMessage functionality.

This module contains the business logic for processing incoming iMessage webhooks
from BlueBubbles and forwarding them to the Brain service.
"""
from app.services.client import BlueBubblesClient

from shared.models.imessage import iMessage
from shared.models.proxy import MultiTurnRequest
from shared.models.contacts import Contact

from shared.log_config import get_logger
logger = get_logger(f"imessage.{__name__}")

import os
import httpx

from datetime import datetime
from fastapi import HTTPException, Request, status


async def receive_webhook(request: Request, bb_client: BlueBubblesClient, timeout: int):
    """
    Handle incoming iMessage webhook from BlueBubbles server.

    This asynchronous function processes incoming webhook payloads from BlueBubbles,
    filtering and transforming new messages before forwarding them to the Brain service.
    Supports automatic reply generation and message forwarding.

    Args:
        request (Request): The incoming HTTP request containing the webhook payload.
        bb_client (BlueBubblesClient): The BlueBubbles client instance.
        timeout (int): Request timeout value.

    Returns:
        dict: A status response indicating message processing result.

    Raises:
        HTTPException: If payload processing fails or is invalid.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.exception("Failed to parse JSON payload from webhook request")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    logger.debug(f"Received webhook payload: {payload}")

    payload_type = payload.get("type")
    if payload_type != "new-message":
        return {
            "status": "ignored",
            "reason": "Not a new-message payload"
        }

    data = payload.get("data", {})
    is_from_me = data.get("isFromMe", False)
    if is_from_me:
        return {
            "status": "ignored",
            "reason": "Self-authored message"
        }

    handle = data.get("handle", {})
    sender_id = handle.get("address")
    text = data.get("text")

    date_created = data.get("dateCreated")
    if date_created:
        try:
            timestamp = datetime.fromtimestamp(date_created / 1000).isoformat()
        except Exception as e:
            logger.warning(f"Failed to parse dateCreated: {date_created}")
            timestamp = datetime.now().isoformat()
    else:
        timestamp = datetime.now().isoformat()

    chats = data.get("chats", [])
    if chats and isinstance(chats, list) and chats[0].get("guid"):
        chat_id = chats[0]["guid"]
    else:
        chat_id = data.get("guid", "")

    imessage = iMessage(
        id=chat_id,
        author_id=sender_id,
        timestamp=str(timestamp),
        content=text
    )

    # Contact lookup
    contacts_port = os.getenv('CONTACTS_PORT', 4205)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            contacts_response = await client.get(
                f"http://contacts:{contacts_port}/search",
                params={"key": "imessage", "value": sender_id}
            )
    except Exception as e:
        logger.exception(f"Exception during contact lookup for sender_id={sender_id}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to contact Contacts service"
        )

    if contacts_response.status_code != status.HTTP_200_OK:
        logger.error(f"Failed to resolve sender address: {contacts_response.status_code} {contacts_response.text}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve sender address: {contacts_response.status_code} {contacts_response.text}"
        )

    try:
        contacts_data = contacts_response.json()
    except Exception as e:
        logger.exception("Failed to parse Contacts service response as JSON")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Contacts service returned invalid JSON"
        )
    if not contacts_data:
        logger.warning(f"No contact found for address: {sender_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    contact: Contact = contacts_data
    user_id = contact.get("id")
    if not user_id:
        logger.error(f"Contact {sender_id} does not have a user_id")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Contact does not have a user_id: {sender_id}"
        )

    payload = MultiTurnRequest(
        model="imessage",
        platform="imessage",
        messages=[
            {
                "role": "user",
                "content": imessage.content
            }
        ],
        user_id=user_id
    )

    # Forward to Brain
    brain_port = os.getenv('BRAIN_PORT', 4207)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            brain_response = await client.post(
                f"http://brain:{brain_port}/api/multiturn",
                json=payload.model_dump()
            )
    except Exception as e:
        logger.exception("Exception during forwarding to Brain service")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to contact Brain service"
        )

    # Send reply if available
    if brain_response.status_code == status.HTTP_200_OK:
        try:
            reply_payload = brain_response.json()
            kirishima_reply = reply_payload.get("response", {})
            if kirishima_reply:
                try:
                    bb_client.send_message(sender_id, kirishima_reply)
                    logger.info(f"✅ Sent Kirishima's reply to {sender_id}")
                except Exception as e:
                    logger.exception("Failed to send reply via BlueBubbles")
        except Exception as e:
            logger.exception("Failed to extract or send reply from Brain response")

    return {"status": "processed"}
