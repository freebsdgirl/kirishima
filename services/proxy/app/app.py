"""
This module defines the main FastAPI application and includes the following functionalities:

- Integration of routers for documentation, API, and iMessage services.
- A health check endpoint (`/ping`) to verify the service status.
- An endpoint (`/__list_routes__`) to list all registered API routes in the application.

Modules:
    - app.docs: Contains the router for documentation-related endpoints.
    - app.api: Contains the router for API-related endpoints.
    - app.imessage: Contains the router for iMessage-related endpoints.

Endpoints:
    - `/ping`: Returns the service status as a JSON response.
    - `/__list_routes__`: Returns a list of all registered routes and their supported HTTP methods.

Attributes:
    app (FastAPI): The main FastAPI application instance.

"""

from app.docs import router as docs_router
from app.api import router as api_router
from app.imessage import router as imessage_router


from fastapi import FastAPI
from fastapi.routing import APIRoute
app = FastAPI()
app.include_router(docs_router, tags=["docs"])
app.include_router(api_router, tags=["api"])
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
