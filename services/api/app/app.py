"""
This module defines the FastAPI application and includes various routers for handling
different API endpoints. The application is configured with the following features:

Routers:
- `routes_router`: Handles system-related routes.
- `docs_router`: Provides API documentation routes.
- `singleturn_router`: Manages single-turn completion endpoints.
- `multiturn_router`: Manages multi-turn completion endpoints.
- `embeddings_router`: Handles embedding-related endpoints.
- `get_model_router`: Retrieves information about a specific model.
- `list_models_router`: Lists all available models.

Tracing:
- If tracing is enabled (`shared.config.TRACING_ENABLED`), the application sets up
    tracing using the `setup_tracing` function from the `shared.tracing` module.

Dependencies:
- FastAPI is used to create the application and manage routing.
- Shared configurations and tracing utilities are imported from the `shared` module.
"""

from app.completions.singleturn import router as singleturn_router
from app.completions.multiturn import router as multiturn_router
from app.v1.embeddings import router as embeddings_router
from app.models.getmodel import router as get_model_router
from app.models.listmodels import router as list_models_router
from app.docs import router as docs_router
from shared.routes import router as routes_router

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI

app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])
app.include_router(singleturn_router, tags=["completions"])
app.include_router(multiturn_router, tags=["completions"])
app.include_router(embeddings_router, tags=["embeddings"])
app.include_router(get_model_router, tags=["models"])
app.include_router(list_models_router, tags=["models"])


import shared.config
if shared.config.TRACING_ENABLED:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="api")
