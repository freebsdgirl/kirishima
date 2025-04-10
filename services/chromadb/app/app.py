"""
This module defines the main FastAPI application and includes various routers for different functionalities.

Routers:
    - memory_router: Handles routes related to memory operations, prefixed with "/memory".
    - summarize_router: Handles routes related to summarization, prefixed with "/summary".
    - buffer_router: Handles routes related to buffer operations, prefixed with "/buffer".
    - docs_router: Handles routes related to documentation, prefixed with "/docs".

Endpoints:
    - /ping: A health check endpoint that returns the service status.
    - /__list_routes__: An endpoint to list all registered API routes in the application.

Attributes:
    app (FastAPI): The main FastAPI application instance.
"""

from app.memory import router as memory_router
from app.summarize import router as summarize_router
from app.buffer import router as buffer_router
from app.docs import router as docs_router


from fastapi import FastAPI
from fastapi.routing import APIRoute
app = FastAPI()
app.include_router(memory_router, prefix="/memory", tags=["memory"])
app.include_router(summarize_router, prefix="/summary", tags=["summary"])
app.include_router(buffer_router, prefix="/buffer", tags=["buffer"])
app.include_router(docs_router, prefix="/docs", tags=["docs"])


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
