"""
Main FastAPI application entrypoint for the Google API service.
- Loads configuration from `/app/config/config.json`.
- Sets up logging, middleware, and routers for system, documentation, and Gmail endpoints.
- Manages application lifespan with startup and shutdown hooks:
    - On startup, optionally starts Gmail email monitoring if enabled in config.
    - On shutdown, stops Gmail email monitoring and cleans up background tasks.
- Registers additional list routes and tracing if enabled in configuration.
Modules imported:
    - shared.log_config: Logging setup.
    - shared.docs_exporter: Documentation routes.
    - shared.routes: System routes and route registration.
    - shared.models.middleware: Custom middleware for caching request bodies.
    - app.routes.gmail: Gmail-specific API routes.
    - app.services.gmail.monitor: Email monitoring service (imported as needed).
    - shared.tracing: Distributed tracing setup (optional).
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.models.middleware import CacheRequestBodyMiddleware

from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
import json

from app.routes.gmail import router as gmail_router

# Load config
with open('/app/config/config.json') as f:
    _config = json.load(f)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    # Startup
    monitor_task = None
    try:
        config = _config
        if config.get('gmail', {}).get('monitor', {}).get('enabled', False):
            logger.info("Starting email monitoring on startup")
            from app.services.gmail.monitor import start_email_monitoring
            # Start monitoring in the background
            monitor_task = asyncio.create_task(start_email_monitoring())
    except Exception as e:
        logger.error(f"Error starting email monitoring: {e}")
    
    yield
    
    # Shutdown
    try:
        logger.info("Stopping email monitoring on shutdown")
        from app.services.gmail.monitor import stop_email_monitoring
        stop_email_monitoring()
        if monitor_task and not monitor_task.done():
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
    except Exception as e:
        logger.error(f"Error stopping email monitoring: {e}")

app = FastAPI(lifespan=lifespan)
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])

app.include_router(gmail_router, tags=["gmail"], prefix="/gmail")

register_list_routes(app)

if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="googleapi")
