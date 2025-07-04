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

from app.message.multiturn import router as message_multiturn_router
from app.message.singleturn import router as message_singleturn_router

from app.summary.periodic import router as periodic_summary_router
from app.summary.daily import router as daily_summary_router
from app.summary.weekly import router as weekly_summary_router
from app.summary.monthly import router as monthly_summary_router

from app.embedding import router as embedding_router

from app.notification.callback import router as notification_callback_router
from app.notification.get import router as notification_get_router
from app.notification.post import router as notification_post_router

from app.memories.scan import router as memory_scan_router
from app.memories.search import router as memory_search_router
from app.memories.add import router as memory_add_router
from app.memories.delete import router as memory_delete_router
from app.memories.list import router as memory_list_router
from app.memories.topic import router as memory_topic_router
from app.memories.patch import router as memory_patch_router
from app.memories.dedup.by_topic import router as memory_dedup_by_topic_router
from app.memories.dedup.topics import router as memory_dedup_topics_router
from app.memories.dedup.keywords import router as memory_dedup_keywords_router

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

app.include_router(memory_scan_router, tags=["memory"])
app.include_router(memory_search_router, tags=["memory"])
app.include_router(memory_add_router, tags=["memory"])
app.include_router(memory_delete_router, tags=["memory"])
app.include_router(memory_list_router, tags=["memory"])
app.include_router(memory_topic_router, tags=["memory"])
app.include_router(memory_patch_router, tags=["memory"])

app.include_router(memory_dedup_by_topic_router, tags=["memory"])
app.include_router(memory_dedup_topics_router, tags=["memory"])
app.include_router(memory_dedup_keywords_router, tags=["memory"])

app.include_router(message_multiturn_router, tags=["message"])
app.include_router(message_singleturn_router, tags=["message"])

app.include_router(embedding_router, tags=["embedding"])

app.include_router(notification_callback_router, tags=["notification"])
app.include_router(notification_get_router, tags=["notification"])
app.include_router(notification_post_router, tags=["notification"])

app.include_router(daily_summary_router, tags=["summary"])
app.include_router(weekly_summary_router, tags=["summary"])
app.include_router(monthly_summary_router, tags=["summary"])
app.include_router(periodic_summary_router, tags=["summary"])

register_list_routes(app)

import json
with open('/app/config/config.json') as f:
    _config = json.load(f)
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="brain")