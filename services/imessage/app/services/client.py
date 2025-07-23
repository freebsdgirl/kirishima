"""
BlueBubbles client for iMessage integration.

This module provides the BlueBubblesClient class for interacting with the BlueBubbles server
to send iMessages via its API.
"""
from shared.log_config import get_logger
logger = get_logger(f"imessage.{__name__}")

import httpx
from fastapi import status

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
        with httpx.Client() as client:
            response = client.post(url, json=payload, params=params)
            response.raise_for_status()
            return response.json()


    def send_message(self, address: str, message: str):
        """
        Send a message to an existing chat using the BlueBubbles API.
        If the chat doesn't exist, attempts to create it and send the message.

        Args:
            address (str): The phone number or contact address.
            message (str): The text message to send.

        Returns:
            dict: The JSON response from BlueBubbles.
        """
        try:
            url = f"{self.base_url}/api/v1/message/text"
            payload = {
                "chatGuid": f"iMessage;+;{address}",
                "message": message,
                "method": "private-api"
            }

            logger.debug(f"Sending payload to BlueBubbles: {payload}")
            params = {"password": self.password}
            with httpx.Client() as client:
                response = client.post(url, json=payload, params=params)
                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR and "Chat does not exist" in e.response.text:
                logger.info("Chat does not exist, attempting to create new chat")
                return self.create_chat_and_send(address, message)
            raise
