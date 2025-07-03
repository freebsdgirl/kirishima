"""
Main application entry point for the scheduler service.

- Initializes FastAPI app with custom middleware for caching request bodies.
- Registers routers for system routes, documentation, job pausing, and job management.
- Registers additional list routes.
- Configures distributed tracing if enabled in the shared configuration.
- Starts the background scheduler.

Modules imported:
    - shared.docs_exporter: Documentation routes.
    - shared.routes: System routes and route registration.
    - app.pause: Job pause management routes.
    - app.jobs: Job management routes.
    - shared.log_config: Logger configuration.
    - app.util: Scheduler utilities.
    - shared.models.middleware: Middleware for caching request bodies.
    - shared.tracing: Tracing setup (conditionally imported).

Attributes:
    app (FastAPI): The FastAPI application instance.
    logger (Logger): Logger instance for the scheduler app.
"""

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from app.delete import router as delete_router
from app.get import router as get_router
from app.post import router as post_router
from app.pause import router as pause_router

from shared.log_config import get_logger
logger = get_logger(f"scheduler.{__name__}")

from app.util import scheduler

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI

app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])
app.include_router(pause_router, tags=["jobs"])
app.include_router(delete_router, tags=["jobs"])
app.include_router(get_router, tags=["jobs"])
app.include_router(post_router, tags=["jobs"])

register_list_routes(app)

import json
with open('/app/config/config.json') as f:
    _config = json.load(f)
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="scheduler")

scheduler.start()
