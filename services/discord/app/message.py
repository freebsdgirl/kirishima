"""
This module provides FastAPI endpoints and Discord bot event handlers for processing and sending Discord direct messages (DMs).
Key Components:
---------------
- send_dm: FastAPI POST endpoint to send a DM to a specified Discord user using the bot instance.
- setup: Function to register Discord bot event handlers for message processing and error handling.
Features:
---------
- Validates and sends DMs to users, handling errors and logging failures.
- Processes incoming Discord messages:
    - Ignores messages from bots and users awaiting responses.
    - Handles commands via Discord's commands.Bot.
    - Forwards DMs to an external "brain" service for processing and relays the response.
    - Logs and raises HTTP exceptions for errors in communication with external services.
- Captures and logs unhandled errors in Discord bot events.
Dependencies:
-------------
- FastAPI for API routing and exception handling.
- httpx for asynchronous HTTP requests.
- shared modules for configuration, logging, and data models.
- Discord.py for bot event handling.
"""
from shared.models.discord import SendDMRequest
from shared.models.proxy import MultiTurnRequest
from shared.models.contacts import Contact
from shared.log_config import get_logger
logger = get_logger(f"discord.{__name__}")

import httpx
import json
import os

from fastapi import HTTPException, status, APIRouter, Request
router = APIRouter()

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


@router.post("/dm")
async def send_dm(request: Request, payload: SendDMRequest):
    """
    Send a direct message (DM) to a specified Discord user.

    Args:
        request (Request): The FastAPI request object containing the bot state.
        payload (SendDMRequest): A request payload containing the target user ID and message content.

    Returns:
        dict: A status response indicating successful message delivery.

    Raises:
        HTTPException: 404 if the user is not found, 500 for other sending errors.
    """
    bot = request.app.state.bot

    try:
        user = await bot.fetch_user(payload.user_id)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"User not found: {payload.user_id}"
            )
        
        await user.send(payload.content)
        
        return {
            "status": "success",
            "message": f"DM sent to user {payload.user_id}"}

    except Exception as e:
        logger.exception(f"Failed to send DM to {payload.user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


def setup(bot):
    """
    Set up Discord bot event handlers for message processing and error handling.
    
    This function configures two primary event handlers:
    1. on_message: Handles incoming Discord messages, processing DMs by forwarding them 
       to a brain service and responding accordingly. Includes logic to:
       - Ignore bot messages
       - Skip processing for users awaiting a response
       - Handle commands
       - Forward DMs to a brain service
       - Send responses back to the user
    
    2. on_error: Captures and logs unhandled errors in Discord bot events.
    
    Args:
        bot (discord.Client): The Discord bot instance to attach event handlers to.
    """
    @bot.event
    async def on_message(message):
        try:
            logger.debug(f"Received message: {message.clean_content}")
            ctx = await bot.get_context(message)

            # 1) Never ignore your own bot
            if message.author.bot:
                return

            # 2) If we’re awaiting this user, skip all custom logic
            if message.author.id in bot.awaiting_response:
                # (you can still choose to process_commands here if needed)
                return

            # if it's a valid command, let commands.Bot handle it and then return
            if ctx.command is not None:
                await bot.process_commands(message)
                return
            
            # only process DMs for now.
            if message.guild is None:
                print(f"Received DM from {message.author.name} ({message.author.id}): {message.clean_content}")
                logger.debug(f"Received DM from {message.author.name} ({message.author.id}): {message.clean_content}")
                
                # Contact lookup
                contacts_port = os.getenv('CONTACTS_PORT', 4205)
                try:
                    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                        contacts_response = await client.get(
                            f"http://contacts:{contacts_port}/search",
                            params={"key": "discord_id", "value": message.author.id}
                        )
                except Exception as e:
                    logger.exception(f"Exception during contact lookup for sender_id={message.author.id}")
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
                    logger.warning(f"No contact found for address: {message.author.id}")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Contact not found"
                    )
                contact: Contact = contacts_data
                user_id = contact.get("id")
                if not user_id:
                    logger.error(f"Contact {message.author.id} does not have a user_id")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Contact does not have a user_id: {message.author.id}"
                    )

                request = MultiTurnRequest(
                    model="discord",
                    platform="discord",
                    messages=[{
                        "role": "user",
                        "content": message.clean_content
                    }],
                    user_id=user_id
                )


                
                try:
                    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                        brain_port = os.getenv("BRAIN_PORT", 4207)
                    
                        response = await client.post(
                            f"http://brain:{brain_port}/api/multiturn", json=request.model_dump())
                        response.raise_for_status()
                        proxy_response = response.json()
                        print(f"RESPONSE {proxy_response}")
                        await ctx.send(proxy_response['response'])

                except httpx.HTTPStatusError as http_err:
                    logger.error(f"HTTP error forwarding from brain: {http_err.response.status_code} - {http_err.response.text}")

                    raise HTTPException(
                        status_code=http_err.response.status_code,
                        detail=f"Error from brain: {http_err.response.text}"
                    )

                except httpx.RequestError as req_err:
                    logger.error(f"Request error when contacting brain: {req_err}")

                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Connection error: {req_err}"
                    )
                
                except Exception as e:
                    logger.exception("Error retrieving service address for brain:", e)
                
            await bot.process_commands(message)  # Ensure commands still work
        except Exception as e:
            logger.exception("Exception in on_message handler")

    @bot.event
    async def on_error(event_method, *args, **kwargs):
        print(f"Unhandled error in event: {event_method}")
        logger.exception(f"Unhandled error in event: {event_method}")
