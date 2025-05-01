"""
This module initializes and configures the FastAPI application for the "brain" service.

It includes:
- Middleware for caching request bodies.
- Routers for various functionalities such as modes, scheduler, memory, messaging, models, embedding, Discord DM, and user summaries.
- System and documentation routes.
- Dynamic route registration.
- Optional tracing setup if enabled in the shared configuration.

Modules and functionalities:
- `app.modes`: Handles mode-related operations.
- `app.scheduler.scheduler`: Manages scheduling tasks.
- `app.memory.functions` and `app.memory.list`: Provide memory-related functionalities.
- `app.message.multiturn` and `app.message.singleturn`: Handle multi-turn and single-turn messaging, respectively.
- `app.summary.user`: Manages user summary operations.
- `app.models`: Handles model-related operations.
- `app.embedding`: Manages embedding-related functionalities.
- `app.discord.dm`: Handles Discord direct messaging.
- `shared.docs_exporter`: Exports API documentation.
- `shared.routes`: Manages system routes and dynamic route registration.
- `shared.models.middleware.CacheRequestBodyMiddleware`: Middleware for caching request bodies.
- `shared.tracing`: Optional tracing setup for monitoring and debugging.

Environment-specific behavior:
- If `TRACING_ENABLED` is set in the shared configuration, tracing is initialized for the application.
"""

from app.modes import router as modes_router
from app.scheduler.scheduler import router as scheduler_router
from app.memory.functions import router as memory_functions_router
from app.memory.list import router as memory_list_router
from app.message.multiturn import router as message_multiturn_router
from app.message.singleturn import router as message_singleturn_router
from app.summary.create_user_periodic_summary import router as create_user_periodic_summary_router
from app.summary.daily import router as daily_summary_router
from app.summary.weekly import router as weekly_summary_router
from app.summary.monthly import router as monthly_summary_router
from app.summary.user import router as user_summary_router
from app.models import router as models_router
from app.embedding import router as embedding_router
from app.discord.dm import router as discord_dm_router

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.models.middleware import CacheRequestBodyMiddleware

from fastapi import FastAPI
app = FastAPI()

app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])
app.include_router(modes_router, tags=["modes"])
app.include_router(scheduler_router, tags=["scheduler"])
app.include_router(memory_functions_router, tags=["memory"])
app.include_router(memory_list_router, tags=["memory"])
app.include_router(message_multiturn_router, tags=["message"])
app.include_router(message_singleturn_router, tags=["message"])
app.include_router(models_router, tags=["models"])
app.include_router(embedding_router, tags=["embedding"])
app.include_router(discord_dm_router, tags=["discord"])
app.include_router(daily_summary_router, tags=["summary"])
app.include_router(weekly_summary_router, tags=["summary"])
app.include_router(monthly_summary_router, tags=["summary"])
app.include_router(user_summary_router, tags=["summary"])
app.include_router(create_user_periodic_summary_router, tags=["summary"])

register_list_routes(app)

import shared.config
if shared.config.TRACING_ENABLED:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="brain")