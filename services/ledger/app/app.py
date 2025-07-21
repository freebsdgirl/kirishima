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
from app.summary.delete import router as summary_delete_router
from app.summary.get import router as summary_get_router
from app.summary.post import router as summary_post_router

from app.user.delete import router as user_delete_router
from app.user.get import router as user_get_router
from app.user.sync import router as user_sync_router

# Memory management routers
from app.memory.create import router as memory_create_router
from app.memory.get import router as memory_get_router
from app.memory.get_list import router as memory_get_list_router
from app.memory.get_by_topic import router as memory_get_by_topic_router
from app.memory.patch import router as memory_patch_router
from app.memory.delete import router as memory_delete_router
from app.memory.search import router as memory_search_router
from app.memory.scan import router as memory_scan_router
from app.memory.assign_topic_to_memory import router as memory_assign_topic_router
from app.memory.dedup import router as memory_dedup_router
from app.memory.dedup_topic_based import router as memory_dedup_topic_based_router
from app.memory.dedup_semantic import router as memory_dedup_semantic_router
# Topic management routers
from app.topic.create import router as topic_create_router
from app.topic.delete import router as topic_delete_router
from app.topic.get_all_topics import router as topic_get_all_router
from app.topic.get_messages_by_topic import router as topic_get_messages_by_topic_router
from app.topic.get_recent_topics import router as topic_get_recent_router
from app.topic.get_topic_by_id import router as topic_get_topic_by_id_router
from app.topic.get_topic_ids_timeframe import router as topic_get_topic_ids_timeframe_router
from app.topic.update import router as topic_update_router
from app.topic.dedup_semantic import router as topic_dedup_semantic_router

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
app.include_router(summary_delete_router, tags=["summary"])
app.include_router(summary_get_router, tags=["summary"])
app.include_router(summary_post_router, tags=["summary"])
app.include_router(user_delete_router, tags=["user"])
app.include_router(user_get_router, tags=["user"])
app.include_router(user_sync_router, tags=["user"])

# Memory management endpoints
app.include_router(memory_create_router, tags=["memory"])
app.include_router(memory_get_router, tags=["memory"])
app.include_router(memory_get_list_router, tags=["memory"])
app.include_router(memory_get_by_topic_router, tags=["memory"])
app.include_router(memory_patch_router, tags=["memory"])
app.include_router(memory_delete_router, tags=["memory"])
app.include_router(memory_search_router, tags=["memory"])
app.include_router(memory_scan_router, tags=["memory"])
app.include_router(memory_assign_topic_router, tags=["memory"])
app.include_router(memory_dedup_router, tags=["memory"])
app.include_router(memory_dedup_topic_based_router, tags=["memory"])
app.include_router(memory_dedup_semantic_router, tags=["memory"])

# Topic management endpoints
app.include_router(topic_create_router, tags=["topic"])
app.include_router(topic_delete_router, tags=["topic"])
app.include_router(topic_get_all_router, tags=["topic"])
app.include_router(topic_get_messages_by_topic_router, tags=["topic"])
app.include_router(topic_get_recent_router, tags=["topic"])
app.include_router(topic_get_topic_by_id_router, tags=["topic"])
app.include_router(topic_get_topic_ids_timeframe_router, tags=["topic"])
app.include_router(topic_update_router, tags=["topic"])
app.include_router(topic_dedup_semantic_router, tags=["topic"])

register_list_routes(app)

import json
with open('/app/config/config.json') as f:
    _config = json.load(f)
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="ledger")
