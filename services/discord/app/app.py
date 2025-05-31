from app.config import DISCORD_TOKEN

from app.registration import setup as registration_setup
from app.message import setup as message_setup

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI

import discord
from discord.ext import commands
import asyncio

from app.message import router as message_router

app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])
app.include_router(message_router, tags=["message"])

register_list_routes(app)

import json
with open('/app/shared/config.json') as f:
    _config = json.load(f)
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="discord")


intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True  # Add this
intents.dm_messages = True      # Add this if available

bot = commands.Bot(command_prefix="!", intents=intents)

app.state.bot = bot  # Store the bot instance in the FastAPI app state

# keep track of user IDs we’re currently waiting on
bot.awaiting_response = set()

registration_setup(bot)
message_setup(bot)

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")


# --- Run Discord Bot in Background ---
def start_bot():
    loop = asyncio.get_event_loop()
    loop.create_task(bot.start(DISCORD_TOKEN))

try:
    start_bot()
except RuntimeError:
    # If already running inside an event loop (e.g., with uvicorn), use create_task
    asyncio.get_event_loop().create_task(bot.start(DISCORD_TOKEN))

