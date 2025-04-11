"""
This module defines the main FastAPI application and includes the following functionalities:

- Registers routers for different parts of the application:
    - `docs_router`: Handles documentation-related endpoints.
    - `singleturn_router`: Handles single-turn API endpoints.
    - `multiturn_router`: Handles multi-turn API endpoints.
    - `imessage_router`: Handles iMessage-related endpoints.

- Provides a health check endpoint (`/ping`) to verify the service status.

- Provides an endpoint (`/__list_routes__`) to list all registered API routes in the application.

Attributes:
        app (FastAPI): The main FastAPI application instance.

Endpoints:
        - `/ping`: Health check endpoint that returns the service status.
        - `/__list_routes__`: Lists all registered API routes with their paths and supported HTTP methods.
"""

from app.docs import router as docs_router
from app.api.models import router as models_router
from app.api.singleturn import router as singleturn_router
from app.api.multiturn import router as multiturn_router
from app.imessage import router as imessage_router


from fastapi import FastAPI
from fastapi.routing import APIRoute
app = FastAPI()
app.include_router(docs_router, tags=["docs"])
app.include_router(models_router, tags=["api", "models"])
app.include_router(singleturn_router, tags=["api"])
app.include_router(multiturn_router, tags=["api"])
app.include_router(imessage_router, tags=["imessage"])


"""
Health check endpoint that returns the service status.

Returns:
    Dict[str, str]: A dictionary with a 'status' key indicating the service is operational.
"""
@app.get("/ping")
def ping():
    return {"status": "ok"}


"""
Endpoint to list all registered API routes in the application.

Returns:
    List[Dict[str, Union[str, List[str]]]]: A list of dictionaries containing route paths and their supported HTTP methods.
"""
@app.get("/__list_routes__")
def list_routes():
    return [
        {"path": route.path, "methods": list(route.methods)}
        for route in app.routes
        if isinstance(route, APIRoute)
    ]
