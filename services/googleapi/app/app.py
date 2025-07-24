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
from app.routes.contacts import router as contacts_router
from app.routes.calendar import router as calendar_router
from app.routes.tasks import router as tasks_router

# Load config
with open('/app/config/config.json') as f:
    _config = json.load(f)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    # Startup
    gmail_monitor_task = None
    calendar_monitor_task = None
    tasks_monitor_task = None
    try:
        config = _config
        
        # Initialize contacts database
        logger.info("Initializing contacts database")
        from app.services.contacts.database import init_contacts_db
        init_contacts_db()
        
        # Refresh contacts cache on startup if enabled
        if config.get('contacts', {}).get('cache_on_startup', True):
            logger.info("Refreshing contacts cache on startup")
            from app.services.contacts.contacts import refresh_contacts_cache
            # Run cache refresh in background to avoid blocking startup
            import asyncio
            asyncio.create_task(asyncio.to_thread(refresh_contacts_cache))
        
        # Start Gmail monitoring if enabled
        if config.get('gmail', {}).get('monitor', {}).get('enabled', False):
            logger.info("Starting email monitoring on startup")
            from app.services.gmail.monitor import start_email_monitoring
            # Start monitoring in the background
            gmail_monitor_task = asyncio.create_task(start_email_monitoring())
        
        # Start Calendar monitoring if enabled
        if config.get('calendar', {}).get('monitor', {}).get('enabled', False):
            logger.info("Starting calendar monitoring on startup")
            
            # Validate calendar access before starting monitoring
            try:
                from app.services.calendar.auth import validate_calendar_access, get_calendar_summary
                calendar_info = validate_calendar_access()
                calendar_summary = get_calendar_summary()
                logger.info(f"Calendar validation successful: {calendar_summary}")
                
                from app.services.calendar.monitor import start_calendar_monitoring
                # Start monitoring in the background
                calendar_monitor_task = asyncio.create_task(start_calendar_monitoring())
                
            except Exception as e:
                logger.error(f"Calendar validation failed - monitoring disabled: {e}")
                logger.error("Please check your calendar configuration in config.json")
                logger.error("Use GET /calendar/calendars/discover to find available calendars")
        
        # Start Tasks monitoring if enabled
        if config.get('tasks', {}).get('monitor', {}).get('enabled', False):
            logger.info("Starting tasks monitoring on startup")
            
            # Validate tasks access before starting monitoring
            try:
                from app.services.tasks.auth import validate_tasks_access
                tasks_info = validate_tasks_access()
                logger.info(f"Tasks validation successful: {tasks_info['message']}")
                
                from app.services.tasks.monitor import start_tasks_monitoring
                # Start monitoring in the background
                tasks_monitor_task = asyncio.create_task(start_tasks_monitoring())
                
            except Exception as e:
                logger.error(f"Tasks validation failed - monitoring disabled: {e}")
                logger.error("Please check your tasks configuration in config.json")
            
    except Exception as e:
        logger.error(f"Error during startup: {e}")
    
    yield
    
    # Shutdown
    try:
        logger.info("Stopping monitoring services on shutdown")
        
        # Stop Gmail monitoring
        try:
            from app.services.gmail.monitor import stop_email_monitoring
            stop_email_monitoring()
            if gmail_monitor_task and not gmail_monitor_task.done():
                gmail_monitor_task.cancel()
                try:
                    await gmail_monitor_task
                except asyncio.CancelledError:
                    pass
        except Exception as e:
            logger.error(f"Error stopping Gmail monitoring: {e}")
        
        # Stop Calendar monitoring
        try:
            from app.services.calendar.monitor import stop_calendar_monitoring
            stop_calendar_monitoring()
            if calendar_monitor_task and not calendar_monitor_task.done():
                calendar_monitor_task.cancel()
                try:
                    await calendar_monitor_task
                except asyncio.CancelledError:
                    pass
        except Exception as e:
            logger.error(f"Error stopping Calendar monitoring: {e}")
        
        # Stop Tasks monitoring
        try:
            from app.services.tasks.monitor import stop_tasks_monitoring
            stop_tasks_monitoring()
            if tasks_monitor_task and not tasks_monitor_task.done():
                tasks_monitor_task.cancel()
                try:
                    await tasks_monitor_task
                except asyncio.CancelledError:
                    pass
        except Exception as e:
            logger.error(f"Error stopping Tasks monitoring: {e}")
            
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

app = FastAPI(lifespan=lifespan)
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])

app.include_router(gmail_router, tags=["gmail"], prefix="/gmail")
app.include_router(contacts_router, tags=["contacts"], prefix="/contacts")
app.include_router(calendar_router, tags=["calendar"], prefix="/calendar")
app.include_router(tasks_router, tags=["tasks"], prefix="/tasks")

register_list_routes(app)

if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="googleapi")
