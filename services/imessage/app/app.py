"""
This module provides a FastAPI application for handling iMessage interactions via the BlueBubbles server. 
It includes endpoints for health checks, listing routes, sending messages, and receiving webhooks. 
The application integrates with a Brain service for processing incoming messages and generating replies.
Classes:
    BlueBubblesClient: A client for interacting with the BlueBubbles server to send iMessages.
    OutgoingMessage: A Pydantic model representing an outgoing iMessage.
Endpoints:
    /ping (GET): Health check endpoint that returns the service status.
    /__list_routes__ (GET): Lists all registered API routes in the application.
    /imessage/send (POST): Sends an iMessage to a specified recipient via the BlueBubbles server.
    /imessage/recv (POST): Handles incoming iMessage webhooks, processes the message, and forwards it to Brain.
Environment Variables:
    BRAIN_HOST: Hostname or IP address of the Brain service (default: 'localhost').
    BRAIN_PORT: Port number of the Brain service (default: '4207').
    BLUEBUBBLES_HOST: Hostname or IP address of the BlueBubbles server (default: 'localhost').
    BLUEBUBBLES_PORT: Port number of the BlueBubbles server (default: '3000').
    BLUEBUBBLES_PASSWORD: Authentication password for the BlueBubbles server (default: 'bluebubbles').
"""

from app.docs import router as docs_router

from shared.log_config import get_logger
logger = get_logger(__name__)

from pydantic import BaseModel
import requests
import httpx
from datetime import datetime

import os
brain_host = os.getenv('BRAIN_HOST', 'localhost')
brain_port = os.getenv('BRAIN_PORT', '4207')
bluebubbles_host = os.getenv('BLUEBUBBLES_HOST', 'localhost')
bluebubbles_port = os.getenv('BLUEBUBBLES_PORT', '3000')
bluebubbles_password = os.getenv('BLUEBUBBLES_PASSWORD', 'bluebubbles')

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.routing import APIRoute
app = FastAPI()
app.include_router(docs_router, tags=["docs"])


"""
Health check endpoint that returns the service status.

Returns:
    Dict[str, str]: A dictionary with a 'status' key indicating the service is operational.
"""
@app.get("/ping")
def ping():
    return {"status": "ok"}


"""
Endpoint to list all registered API routes in the application.

Returns:
    List[Dict[str, Union[str, List[str]]]]: A list of dictionaries containing route paths and their supported HTTP methods.
"""
@app.get("/__list_routes__")
def list_routes():
    return [
        {"path": route.path, "methods": list(route.methods)}
        for route in app.routes
        if isinstance(route, APIRoute)
    ]


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


class OutgoingMessage(BaseModel):
    """
    Represents an outgoing iMessage with recipient address and message content.
    
    Attributes:
        address (str): The phone number or contact address to send the message to.
        message (str): The text content of the message to be sent.
    """
    address: str
    message: str


@app.post("/imessage/send")
def send_message(payload: OutgoingMessage):
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
    Handle incoming iMessage webhook, process the message, and forward it to Brain for potential response.

    Receives a webhook payload from BlueBubbles, validates the message, extracts relevant details,
    and forwards the standardized message to Brain's incoming message endpoint. If Brain provides
    a reply, the message is sent back to the original sender via BlueBubbles.

    Args:
        request (Request): The incoming webhook request containing the iMessage payload.

    Returns:
        dict: A status response indicating the message was processed and forwarded.

    Raises:
        HTTPException: If the payload is invalid or cannot be processed.
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

        # Build the standardized payload for Brain
        incoming_message_payload = {
            "platform": "imessage",
            "sender_id": sender_id,
            "text": text,
            "timestamp": timestamp,
            "metadata": {"chat_id": chat_id}
        }

        # Forward the standardized payload to Brain's /message/incoming endpoint
        async with httpx.AsyncClient(timeout=30) as client:
            brain_response = await client.post(
                f"http://{brain_host}:{brain_port}/message/incoming",
                json=incoming_message_payload
            )

        logger.debug(
            f"Forwarded payload to Brain: {incoming_message_payload} "
            f"with response: {brain_response.status_code} {brain_response.text}"
        )


        # Send the reply back via BlueBubbles
        if brain_response.status_code == status.HTTP_200_OK:
            try:
                reply_payload = brain_response.json()
                kirishima_reply = reply_payload.get("reply", {}).get("reply")

                if kirishima_reply:
                    bb_client.send_message(sender_id, kirishima_reply)
                    logger.info(f"✅ Sent Kirishima's reply to {sender_id}")

            except Exception as e:
                logger.exception("⚠️ Failed to extract or send reply from Brain")

        return {"status": "received and forwarded"}

    except Exception as e:
        logger.exception("Failed to process webhook payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload"
        )
