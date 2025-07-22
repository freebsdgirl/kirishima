"""
Main application entry point for the Ledger service.

- Initializes the buffer database.
- Sets up FastAPI application with custom middleware.
- Includes routers for system, documentation, user-related endpoints, topics, and memory management.
- Registers additional list routes.
- Loads configuration from JSON file and conditionally enables tracing if specified.

Modules imported:
    - User routers: delete, get, sync
    - Topic routers: all topic management endpoints
    - Memory routers: all memory management endpoints including deduplication
    - Setup: buffer database initialization
    - Shared: docs exporter, routes, middleware, tracing

Environment:
    - Expects configuration at '/app/config/config.json'
"""

from app.summary.create.summary import router as summary_create_router
from app.summary.get import router as summary_get_router
from app.summary.post import router as summary_post_router

from app.user.delete import router as user_delete_router
from app.user.get import router as user_get_router
from app.user.sync import router as user_sync_router

from app.routes.memory import router as memory_router
from app.routes.topic import router as topic_router
from app.routes.summary import router as summary_router
from app.routes.context import router as context_router


# Topic management routers
from app.topic.create import router as topic_create_router
from app.topic.delete import router as topic_delete_router
from app.topic.get_all_topics import router as topic_get_all_router
from app.topic.get_messages_by_topic import router as topic_get_messages_by_topic_router
from app.topic.get_recent_topics import router as topic_get_recent_router
from app.topic.get_topic_by_id import router as topic_get_topic_by_id_router
from app.topic.get_topic_ids_timeframe import router as topic_get_topic_ids_timeframe_router
from app.topic.update import router as topic_update_router

from app.setup import init_buffer_db

init_buffer_db()

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI

app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])
app.include_router(summary_create_router, tags=["summary"])
app.include_router(summary_get_router, tags=["summary"])
app.include_router(summary_post_router, tags=["summary"])
app.include_router(user_delete_router, tags=["user"])
app.include_router(user_get_router, tags=["user"])
app.include_router(user_sync_router, tags=["user"])

# Memory management endpoints
app.include_router(memory_router, tags=["memories"], prefix="/memories")
app.include_router(topic_router, tags=["topics"], prefix="/topics")
app.include_router(summary_router, tags=["summary"], prefix="/summary")
app.include_router(context_router, tags=["context"], prefix="/context")

# Topic management endpoints
app.include_router(topic_create_router, tags=["topic"])
app.include_router(topic_delete_router, tags=["topic"])
app.include_router(topic_get_all_router, tags=["topic"])
app.include_router(topic_get_messages_by_topic_router, tags=["topic"])
app.include_router(topic_get_recent_router, tags=["topic"])
app.include_router(topic_get_topic_by_id_router, tags=["topic"])
app.include_router(topic_get_topic_ids_timeframe_router, tags=["topic"])
app.include_router(topic_update_router, tags=["topic"])

register_list_routes(app)

import json
with open('/app/config/config.json') as f:
    _config = json.load(f)
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="ledger")
