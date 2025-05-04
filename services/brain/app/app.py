"""
This module initializes and configures the FastAPI application for the "brain" service.

It includes the following functionalities:
- Middleware setup:
    - `CacheRequestBodyMiddleware` for caching request bodies.
- Router inclusion:
    - System routes for internal operations.
    - Documentation routes for API documentation.
    - Mode-related routes for handling application modes.
    - Scheduler routes for task scheduling.
    - Memory-related routes for managing memory functions and lists.
    - Message-related routes for single-turn and multi-turn message handling.
    - Model routes for managing AI models.
    - Embedding routes for embedding-related operations.
    - Discord DM routes for handling Discord direct messages.
    - Summary routes for daily, weekly, monthly, user-specific, and periodic summaries.
- Dynamic route registration using `register_list_routes`.
- Optional tracing setup if tracing is enabled in the shared configuration.

Dependencies:
- `shared.config` for configuration management.
- `shared.tracing` for tracing setup when enabled.

The application is designed to be modular and extensible, allowing for easy integration of additional features or services.
"""

from app.modes import router as modes_router
from app.scheduler.scheduler import router as scheduler_router

from app.memory.delete import router as memory_delete_router
from app.memory.get import router as memory_get_router
from app.memory.post import router as memory_post_router

from app.message.multiturn import router as message_multiturn_router
from app.message.singleturn import router as message_singleturn_router

from app.summary.periodic import router as periodic_summary_router
from app.summary.daily import router as daily_summary_router
from app.summary.weekly import router as weekly_summary_router
from app.summary.monthly import router as monthly_summary_router

from app.models import router as models_router
from app.embedding import router as embedding_router
from app.discord.dm import router as discord_dm_router
from app.imessage import router as imessage_router

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.models.middleware import CacheRequestBodyMiddleware


from contextlib import asynccontextmanager
from app.setup import verify_database
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    verify_database()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])
app.include_router(modes_router, tags=["modes"])
app.include_router(scheduler_router, tags=["scheduler"])

app.include_router(memory_delete_router, tags=["memory"])
app.include_router(memory_get_router, tags=["memory"])
app.include_router(memory_post_router, tags=["memory"])

app.include_router(message_multiturn_router, tags=["message"])
app.include_router(message_singleturn_router, tags=["message"])

app.include_router(models_router, tags=["models"])
app.include_router(embedding_router, tags=["embedding"])
app.include_router(discord_dm_router, tags=["discord"])
app.include_router(imessage_router, tags=["imessage"])

app.include_router(daily_summary_router, tags=["summary"])
app.include_router(weekly_summary_router, tags=["summary"])
app.include_router(monthly_summary_router, tags=["summary"])
app.include_router(periodic_summary_router, tags=["summary"])

register_list_routes(app)

import shared.config
if shared.config.TRACING_ENABLED:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="brain")