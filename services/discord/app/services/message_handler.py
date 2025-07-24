"""
Message handler service for Discord integration.
This module contains the core message processing logic that was previously in message.py.
"""
from shared.models.proxy import MultiTurnRequest
from shared.log_config import get_logger

import httpx
import json
import os
from fastapi import HTTPException, status

logger = get_logger(f"discord.{__name__}")


class MessageHandlerService:
    """Service for handling Discord message processing and forwarding to brain service."""
    
    def __init__(self):
        with open('/app/config/config.json') as f:
            self._config = json.load(f)
        self.timeout = self._config["timeout"]
        self.brain_port = os.getenv("BRAIN_PORT", 4207)
    
    async def handle_message(self, bot, message, contacts_service):
        """
        Process incoming Discord messages, focusing on direct messages (DMs).
        
        Args:
            bot: Discord bot instance
            message: Discord message object
            contacts_service: ContactsService instance for user resolution
        """
        logger.debug(f"Received message: {message.clean_content}")
        ctx = await bot.get_context(message)

        # 1) Never process bot messages
        if message.author.bot:
            return

        # 2) If we're awaiting this user, skip all custom logic
        if message.author.id in bot.awaiting_response:
            return

        # 3) If it's a valid command, let commands.Bot handle it and return
        if ctx.command is not None:
            await bot.process_commands(message)
            return
        
        # 4) Only process DMs for now
        if message.guild is None:
            await self._handle_dm(bot, message, ctx, contacts_service)
            
        # Ensure commands still work
        await bot.process_commands(message)
    
    async def _handle_dm(self, bot, message, ctx, contacts_service):
        """
        Handle direct message processing.
        
        Args:
            bot: Discord bot instance
            message: Discord message object
            ctx: Discord context object
            contacts_service: ContactsService instance for user resolution
        """
        logger.debug(f"Received DM from {message.author.name} ({message.author.id}): {message.clean_content}")
        
        # Look up contact information
        contact = await contacts_service.get_contact_from_discord_id(message.author.id)
        
        if not contact:
            logger.warning(f"No contact found for Discord ID: {message.author.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact not found"
            )
        
        user_id = contact.get("id")
        if not user_id:
            logger.error(f"Contact {message.author.id} does not have a user_id")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Contact does not have a user_id: {message.author.id}"
            )

        # Create request for brain service
        request = MultiTurnRequest(
            model="discord",
            platform="discord",
            messages=[{
                "role": "user",
                "content": message.clean_content
            }],
            user_id=user_id
        )

        # Forward to brain service and send response
        try:
            response_text = await self._forward_to_brain(request)
            await ctx.send(response_text)
        except Exception as e:
            logger.exception("Error processing DM")
            raise
    
    async def _forward_to_brain(self, request: MultiTurnRequest) -> str:
        """
        Forward request to brain service and return response text.
        
        Args:
            request: MultiTurnRequest to send to brain
            
        Returns:
            str: Response text from brain service
            
        Raises:
            HTTPException: On various error conditions
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"http://brain:{self.brain_port}/api/multiturn", 
                    json=request.model_dump()
                )
                response.raise_for_status()
                proxy_response = response.json()
                return proxy_response['response']

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error forwarding to brain: {http_err.response.status_code} - {http_err.response.text}")
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
            logger.exception("Error retrieving service address for brain")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )
