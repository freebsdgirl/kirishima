"""
Main application entry point for the scheduler service.

This module initializes the FastAPI application, configures middleware,
registers routers for system, documentation, and scheduler endpoints,
and sets up tracing if enabled in the configuration. It also starts the
scheduler process.

Modules and Components:
- shared.docs_exporter: Documentation router.
- shared.routes: System routes and route registration utility.
- app.routes.scheduler: Scheduler-specific API routes.
- shared.log_config: Logger configuration.
- app.util.scheduler: Scheduler utility for background tasks.
- shared.models.middleware: Middleware for caching request bodies.
- shared.tracing: Tracing setup for distributed tracing (optional).

Configuration:
- Loads configuration from '/app/config/config.json'.
- Enables tracing if 'tracing_enabled' is set to True.

Middleware:
- CacheRequestBodyMiddleware: Caches request bodies for downstream processing.

Routers:
- System routes (tag: "system")
- Documentation routes (tag: "docs")
- Scheduler routes (tag: "scheduler", prefix: "/scheduler")

Functions:
- register_list_routes: Registers additional list-related routes.
- scheduler.start: Starts the background scheduler process.
"""

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from app.routes.scheduler import router as scheduler_router


from shared.log_config import get_logger
logger = get_logger(f"scheduler.{__name__}")

from app.util import scheduler

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI

app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])

app.include_router(scheduler_router, prefix="/scheduler", tags=["scheduler"])

register_list_routes(app)

import json
with open('/app/config/config.json') as f:
    _config = json.load(f)
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="scheduler")

scheduler.start()
