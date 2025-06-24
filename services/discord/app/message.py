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
import shared.consul

from shared.models.discord import DiscordDirectMessage, SendDMRequest

from shared.log_config import get_logger
logger = get_logger(f"discord.{__name__}")

import httpx
import json

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

                discord_message = DiscordDirectMessage(
                    message_id=message.id,
                    content=message.clean_content,
                    author_id=message.author.id,
                    display_name=message.author.display_name
                )

                async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                    try:
                        brain_address, brain_port = shared.consul.get_service_address('brain')
                    
                        response = await client.post(
                            f"http://{brain_address}:{brain_port}/discord/message/incoming", json=discord_message.model_dump())
                        response.raise_for_status()
                        proxy_response = response.json()
                        print(f"RESPONSE {proxy_response}")
                        await ctx.send(proxy_response['response'])

                    except httpx.HTTPStatusError as http_err:
                        logger.error(f"HTTP error forwarding from ledger: {http_err.response.status_code} - {http_err.response.text}")

                        raise HTTPException(
                            status_code=http_err.response.status_code,
                            detail=f"Error from ledger: {http_err.response.text}"
                        )

                    except httpx.RequestError as req_err:
                        logger.error(f"Request error when contacting ledger: {req_err}")

                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Connection error: {req_err}"
                        )
                    
                    except Exception as e:
                        logger.exception("Error retrieving service address for ledger:", e)
                
            await bot.process_commands(message)  # Ensure commands still work
        except Exception as e:
            logger.exception("Exception in on_message handler")

    @bot.event
    async def on_error(event_method, *args, **kwargs):
        print(f"Unhandled error in event: {event_method}")
        logger.exception(f"Unhandled error in event: {event_method}")
