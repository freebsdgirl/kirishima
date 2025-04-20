"""
This module initializes and configures the FastAPI application for the intents service.

It includes the following:
- Importing and setting up routers for documentation, system routes, and intents.
- Configuring logging for the application using the shared logging configuration.
- Optionally enabling tracing if the `TRACING_ENABLED` configuration is set to True.

Modules:
- `shared.docs_exporter`: Provides the documentation router.
- `shared.routes`: Provides system-related routes.
- `app.intents`: Provides routes related to intents.
- `shared.log_config`: Configures logging for the application.
- `shared.config`: Contains application configuration settings.
- `shared.tracing`: Sets up tracing for the application (if enabled).

Attributes:
- `app`: The FastAPI application instance.

Conditional:
- If `TRACING_ENABLED` is set to True in the configuration, tracing is initialized for the service.
"""

from app.intents import router as intents_router

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI

app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])
app.include_router(intents_router, tags=["intents"])

register_list_routes(app)

import shared.config
if shared.config.TRACING_ENABLED:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="intents")
