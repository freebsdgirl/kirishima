"""
This module initializes and configures the FastAPI application for the iMessage service.

- Loads configuration from a JSON file.
- Sets up logging and tracing (if enabled).
- Registers middleware and routers for system, documentation, and iMessage endpoints.
- Initializes the BlueBubbles client for iMessage integration.

Modules imported:
    - BlueBubblesClient: Handles communication with the BlueBubbles server.
    - get_logger: Configures logging for the service.
    - FastAPI: Web framework for building the API.
    - CacheRequestBodyMiddleware: Middleware for caching request bodies.
    - docs_router, routes_router, register_list_routes, imessage_router: Routers for API endpoints.

Configuration:
    - Reads from '/app/config/config.json' for service settings.
    - Supports tracing and timeout configuration.
    - BlueBubbles client is configured using the loaded settings.
"""
from app.services.client import BlueBubblesClient

from shared.log_config import get_logger
logger = get_logger(f"imessage.{__name__}")

import json
from fastapi import FastAPI

from shared.models.middleware import CacheRequestBodyMiddleware

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes
from app.routes.imessage import router as imessage_router


# Load configuration
with open('/app/config/config.json') as f:
    _config = json.load(f)

# Initialize FastAPI app
app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

# Setup tracing if enabled
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="imessage")

# Include routers
app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])
app.include_router(imessage_router, tags=["imessage"])

register_list_routes(app)

# Configuration constants
TIMEOUT = _config["timeout"]

bb_config = _config["bluebubbles"]
bluebubbles_host = bb_config["host"]
bluebubbles_port = bb_config["port"]
bluebubbles_password = bb_config["password"]

# Initialize BlueBubbles client
bb_client = BlueBubblesClient(
    base_url=f"http://{bluebubbles_host}:{bluebubbles_port}",
    password=bluebubbles_password
)
