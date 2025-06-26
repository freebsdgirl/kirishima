"""
Main FastAPI application entry point for the Stickynotes service.

- Sets up logging, middleware, and includes routers for various endpoints (system, docs, create, list, resolve, snooze, check).
- Initializes the database during application lifespan.
- Loads configuration from a JSON file and conditionally enables tracing if specified.

Modules imported:
    - shared.docs_exporter: Documentation routes.
    - shared.routes: System routes and route registration.
    - shared.log_config: Logger configuration.
    - shared.models.middleware: Middleware for caching request bodies.
    - app.create, app.list, app.resolve, app.snooze, app.check: Feature-specific routers.
    - app.setup: Database initialization.
    - shared.tracing: Tracing setup (conditionally enabled).

Configuration:
    - Reads from '/app/config/config.json'.
    - Enables tracing if 'tracing_enabled' is set to True.
"""

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.log_config import get_logger
logger = get_logger(f"stickynotes.{__name__}")

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI


from contextlib import asynccontextmanager

from app.create import router as create_router
from app.list import router as list_router
from app.resolve import router as resolve_router
from app.snooze import router as snooze_router
from app.check import router as check_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing stickynotes database via lifespan...")
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])
app.include_router(create_router)
app.include_router(list_router)
app.include_router(resolve_router)
app.include_router(snooze_router)
app.include_router(check_router)

register_list_routes(app)


from app.setup import init_db

import json
with open('/app/config/config.json') as f:
    _config = json.load(f)
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="stickynotes")