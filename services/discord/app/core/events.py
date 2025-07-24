"""
Discord event handlers.
This module contains all Discord event handlers that were previously in message.py.
"""
from app.services.message_handler import MessageHandlerService
from app.services.contacts import ContactsService

from shared.log_config import get_logger
logger = get_logger(f"discord.{__name__}")


def setup_event_handlers(bot):
    """
    Set up all Discord bot event handlers.
    
    Args:
        bot (discord.Client): The Discord bot instance to attach event handlers to.
    """
    message_handler = MessageHandlerService()
    contacts_service = ContactsService()
    
    @bot.event
    async def on_ready():
        """Handle bot ready event."""
        print(f"Bot logged in as {bot.user}")

    @bot.event
    async def on_message(message):
        """Handle incoming Discord messages."""
        try:
            await message_handler.handle_message(bot, message, contacts_service)
        except Exception as e:
            logger.exception("Exception in on_message handler")

    @bot.event
    async def on_error(event_method, *args, **kwargs):
        """Handle unhandled Discord event errors."""
        logger.exception(f"Unhandled error in event: {event_method}")
