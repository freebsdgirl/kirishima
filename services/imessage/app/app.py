"""
This module provides a FastAPI application for handling iMessage integration via the BlueBubbles server.
Features:
- Sends iMessages to specified recipients using BlueBubbles API.
- Receives and processes incoming iMessage webhooks from BlueBubbles.
- Forwards incoming messages to the Brain service for further processing and automated replies.
- Handles chat creation if a chat does not exist when sending a message.
- Includes system and documentation routes, logging, tracing, and request body caching middleware.
Classes:
    BlueBubblesClient: Client for interacting with the BlueBubbles server to send and receive iMessages.
    OutgoingMessage: Pydantic model representing an outgoing iMessage payload.
Endpoints:
    POST /imessage/send: Sends an iMessage to a specified recipient.
    POST /imessage/recv: Receives and processes incoming iMessage webhooks from BlueBubbles.
Environment Variables:
    BLUEBUBBLES_HOST: Hostname of the BlueBubbles server (default: 'localhost').
    BLUEBUBBLES_PORT: Port of the BlueBubbles server (default: '3000').
    BLUEBUBBLES_PASSWORD: Password for authenticating with BlueBubbles (default: 'bluebubbles').
"""

from shared.config import TIMEOUT

from shared.models.imessage import iMessage, OutgoingiMessage

import shared.consul

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.log_config import get_logger
logger = get_logger(__name__)

from pydantic import BaseModel
import requests
import httpx
from datetime import datetime

import os
bluebubbles_host = os.getenv('BLUEBUBBLES_HOST', 'localhost')
bluebubbles_port = os.getenv('BLUEBUBBLES_PORT', '3000')
bluebubbles_password = os.getenv('BLUEBUBBLES_PASSWORD', 'bluebubbles')

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI, HTTPException, Request, status

app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])

register_list_routes(app)

import shared.config
if shared.config.TRACING_ENABLED:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="imessage")


class BlueBubblesClient:
    """
    A client for interacting with the BlueBubbles server to send iMessages.

    This class provides methods to establish a connection with a BlueBubbles server
    and send messages via its API.

    Attributes:
        base_url (str): The base URL of the BlueBubbles server.
        password (str): Authentication password for the server.
    """
    def __init__(self, base_url: str, password: str):
        """
        Initialize a BlueBubblesClient with server connection details.

        Args:
            base_url (str): The base URL of the BlueBubbles server, with trailing slashes removed.
            password (str): Authentication password for the BlueBubbles server.
        """
        self.base_url = base_url.rstrip("/")
        self.password = password

    def create_chat_and_send(self, address: str, message: str):
        """
        Create a new chat and send a message using the BlueBubbles API.

        Args:
            address (str): The phone number or contact address.
            message (str): The text message to send.

        Returns:
            dict: The JSON response from BlueBubbles.
        """
        url = f"{self.base_url}/api/v1/chat/new"
        payload = {
            "addresses": [address],
            "message": message
        }
        params = {"password": self.password}
        logger.debug(f"Creating chat and sending message via BlueBubbles: {payload}")
        response = requests.post(url, json=payload, params=params)
        response.raise_for_status()
        return response.json()

    def send_message(self, address: str, message: str):
        try:
            url = f"{self.base_url}/api/v1/message/text"
            payload = {
                "chatGuid": f"iMessage;+;{address}",
                "message": message,
                "method": "private-api"
            }

            logger.debug(f"Sending payload to BlueBubbles: {payload}")
            params = {"password": self.password}
            response = requests.post(url, json=payload, params=params)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR and "Chat does not exist" in e.response.text:
                logger.info("Chat does not exist, attempting to create new chat")
                return self.create_chat_and_send(address, message)
            raise


# Initialize a BlueBubbles client for sending iMessages using server configuration from environment variables
bb_client = BlueBubblesClient(
    base_url=f"http://{bluebubbles_host}:{bluebubbles_port}",
    password=bluebubbles_password
)


@app.post("/imessage/send")
def send_message(payload: OutgoingiMessage):
    """
    Send an iMessage to a specified recipient via BlueBubbles server.

    Args:
        payload (OutgoingMessage): Contains the recipient's address and message content.

    Returns:
        dict: A response indicating the message was sent, including the server's response.

    Raises:
        HTTPException: If the message sending process fails, with a 500 status code.
    """
    logger.info(f"Sending iMessage to {payload.address}")

    try:
        result = bb_client.send_message(payload.address, payload.message)
        return {
            "status": "sent",
            "response": result
        }

    except requests.exceptions.HTTPError as e:
        logger.warning(f"BlueBubbles returned HTTP error: {e.response.status_code}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.text
        )


@app.post("/imessage/recv")
async def receive_webhook(request: Request):
    """
    Handle incoming iMessage webhook from BlueBubbles server.

    This asynchronous endpoint processes incoming webhook payloads from BlueBubbles,
    filtering and transforming new messages before forwarding them to the Brain service.
    Supports automatic reply generation and message forwarding.

    Args:
        request (Request): The incoming HTTP request containing the webhook payload.

    Returns:
        dict: A status response indicating message processing result.

    Raises:
        HTTPException: If payload processing fails or is invalid.
    """
    try:
        payload = await request.json()
        logger.debug(f"Received webhook payload: {payload}")

        # Check for the type and log all payloads regardless
        payload_type = payload.get("type")
        if payload_type != "new-message":
            logger.debug("Ignoring payload because type is not 'new-message'")
            return {
                "status": "ignored",
                "reason": "Not a new-message payload"
            }

        # Extract the inner data from the payload
        data = payload.get("data", {})

        is_from_me = data.get("isFromMe", False)

        if is_from_me:
            logger.debug("Ignoring message from self (isFromMe=True)")
            return {
                "status": "ignored",
                "reason": "Self-authored message"
            }

        # Extract sender details from the 'handle'
        handle = data.get("handle", {})
        sender_id = handle.get("address")
        text = data.get("text")

        # Convert the dateCreated (in ms) to an ISO 8601 timestamp
        date_created = data.get("dateCreated")
        if date_created:
            timestamp = datetime.fromtimestamp(date_created / 1000).isoformat()
        else:
            timestamp = datetime.now().isoformat()

        # Determine a chat identifier from the 'chats' array, or fallback to the message guid
        chats = data.get("chats", [])
        if chats and isinstance(chats, list) and chats[0].get("guid"):
            chat_id = chats[0]["guid"]
        else:
            chat_id = data.get("guid", "")

        payload = iMessage(
            id=chat_id,
            author_id=sender_id,
            timestamp=str(timestamp),
            content=text
        )

        # Forward the standardized payload to Brain's /message/incoming endpoint
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            brain_address, brain_port = shared.consul.get_service_address('brain')

            brain_response = await client.post(
                f"http://{brain_address}:{brain_port}/imessage/incoming",
                json=payload.model_dump()
            )

        logger.debug(
            f"Forwarded payload to Brain: {payload} "
            f"with response: {brain_response.status_code} {brain_response.text}"
        )

        # Send the reply back via BlueBubbles
        if brain_response.status_code == status.HTTP_200_OK:
            try:
                reply_payload = brain_response.json()
                kirishima_reply = reply_payload.get("response", {})

                if kirishima_reply:
                    bb_client.send_message(sender_id, kirishima_reply)
                    logger.info(f"✅ Sent Kirishima's reply to {sender_id}")

            except Exception as e:
                logger.exception("⚠️ Failed to extract or send reply from Brain")

        logger.debug("Forwarded payload to Brain successfully")

    except Exception as e:
        logger.exception("Failed to process webhook payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload"
        )
