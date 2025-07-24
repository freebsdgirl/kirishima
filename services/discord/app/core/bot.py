"""
Discord bot configuration and initialization.
This module handles the creation and configuration of the Discord bot instance.
"""
import discord
from discord.ext import commands
import json
from typing import Optional

from shared.log_config import get_logger
logger = get_logger(f"discord.{__name__}")


class BotManager:
    """Manages Discord bot instance and lifecycle."""
    
    def __init__(self):
        self.bot: Optional[commands.Bot] = None
        self._config = self._load_config()
        
    def _load_config(self) -> dict:
        """Load configuration from config.json."""
        with open('/app/config/config.json') as f:
            return json.load(f)
    
    def create_bot(self) -> commands.Bot:
        """Create and configure the Discord bot instance."""
        discord_token = self._config.get("discord", {}).get("token", "")
        if not discord_token:
            raise ValueError("Discord token is not set in the configuration.")

        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True
        intents.dm_messages = True

        self.bot = commands.Bot(command_prefix="!", intents=intents)
        
        # Keep track of user IDs we're currently waiting on
        self.bot.awaiting_response = set()
        
        return self.bot


# Global bot manager instance
bot_manager = BotManager()
