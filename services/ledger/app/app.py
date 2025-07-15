"""
Main application entry point for the Ledger service.

- Initializes the buffer database.
- Sets up FastAPI application with custom middleware.
- Includes routers for system, documentation, and user-related endpoints (delete, get, sync).
- Registers additional list routes.
- Loads configuration from JSON file and conditionally enables tracing if specified.

Modules imported:
    - User routers: delete, get, sync
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
from app.topic import router as topics_router

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
app.include_router(topics_router, tags=["topics"])

register_list_routes(app)

import json
with open('/app/config/config.json') as f:
    _config = json.load(f)
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="ledger")
