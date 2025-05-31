"""
This module defines the FastAPI application for the "contacts" service.

The application is configured with the following:
- Middleware for caching request bodies.
- Routers for handling system, documentation, and CRUD operations on contacts.
- Initialization of the database at startup.
- Optional tracing setup if tracing is enabled in the shared configuration.

Modules and Components:
- `shared.docs_exporter`: Provides the documentation router.
- `shared.routes`: Provides the system routes and a function to register additional routes.
- `app.method`: Contains routers for handling POST, GET, PUT, DELETE, and PATCH methods for contacts.
- `app.setup`: Contains the function to initialize the database.
- `shared.log_config`: Configures logging for the application.
- `shared.models.middleware`: Provides middleware for caching request bodies.
- `shared.config`: Contains shared configuration settings.
- `shared.tracing`: Provides tracing setup if enabled.

Key Features:
- Middleware: Adds `CacheRequestBodyMiddleware` to cache request bodies.
- Routers: Includes routers for system, documentation, and CRUD operations on contacts.
- Database Initialization: Ensures the database is initialized at application startup.
- Tracing: Optionally sets up tracing for the service if enabled in the configuration.

Usage:
This module is the entry point for the "contacts" service and should be executed to start the FastAPI application.
"""

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from app.method.post import router as post_router
from app.method.get import router as get_router
from app.method.put import router as put_router
from app.method.delete import router as delete_router
from app.method.patch import router as patch_router

from app.setup import initialize_database

from shared.log_config import get_logger
logger = get_logger(f"contacts.{__name__}")

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI

app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])
app.include_router(post_router, tags=["contacts"])
app.include_router(get_router, tags=["contacts"])
app.include_router(put_router, tags=["contacts"])
app.include_router(delete_router, tags=["contacts"])
app.include_router(patch_router, tags=["contacts"])

register_list_routes(app)

import json
with open('/app/shared/config.json') as f:
    _config = json.load(f)
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="contacts")


# Call initialize_database() at startup
initialize_database()