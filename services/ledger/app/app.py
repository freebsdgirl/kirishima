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

from app.routes.memory import router as memory_router
from app.routes.topic import router as topic_router
from app.routes.summary import router as summary_router
from app.routes.context import router as context_router
from app.routes.user import router as user_router

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

app.include_router(memory_router, tags=["memories"], prefix="/memories")
app.include_router(topic_router, tags=["topics"], prefix="/topics")
app.include_router(summary_router, tags=["summary"], prefix="/summary")
app.include_router(context_router, tags=["context"], prefix="/context")
app.include_router(user_router, tags=["user"], prefix="/user")

register_list_routes(app)

import json
with open('/app/config/config.json') as f:
    _config = json.load(f)
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="ledger")
