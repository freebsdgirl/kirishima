"""
FastAPI application for Discord service.

This module sets up the FastAPI app, includes routers for system, documentation, DM, and health endpoints,
registers additional list routes, loads configuration, and optionally enables tracing. It initializes the Discord bot,
sets up event handlers, and starts the bot in the background using the provided Discord token.

Modules imported:
- FastAPI and middleware
- Shared routers and documentation exporter
- Discord bot manager and event handlers
- JSON and asyncio for configuration and background tasks

Key components:
- FastAPI app initialization and middleware setup
- Router inclusion for various endpoints
- Configuration loading from JSON file
- Optional tracing setup
- Discord bot creation and event handler registration
- Background startup of Discord bot with error handling for event loop context
"""
from fastapi import FastAPI

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes
from shared.models.middleware import CacheRequestBodyMiddleware

from app.routes.dm import router as dm_router
from app.routes.health import router as health_router
from app.core.bot import bot_manager
from app.core.events import setup_event_handlers

import json
import asyncio

# Create FastAPI app
app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

# Include routers
app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])
app.include_router(dm_router, tags=["dm"])
app.include_router(health_router, tags=["health"])

register_list_routes(app)

# Load configuration
with open('/app/config/config.json') as f:
    _config = json.load(f)

# Setup tracing if enabled
if _config.get('tracing_enabled', False):
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="discord")

# Initialize Discord bot
bot = bot_manager.create_bot()
app.state.bot = bot  # Store the bot instance in the FastAPI app state

# Setup Discord event handlers
setup_event_handlers(bot)

# --- Run Discord Bot in Background (preserving original logic) ---
discord_token = _config.get("discord", {}).get("token", "")

def start_bot():
    loop = asyncio.get_event_loop()
    loop.create_task(bot.start(discord_token))

try:
    start_bot()
except RuntimeError:
    # If already running inside an event loop (e.g., with uvicorn), use create_task
    asyncio.get_event_loop().create_task(bot.start(discord_token))
