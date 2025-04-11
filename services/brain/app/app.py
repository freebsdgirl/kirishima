"""
This module defines the main FastAPI application and its routes.

The application includes various routers for handling different functionalities such as memory management, buffering, 
status checks, scheduling, documentation, and message processing. It also provides utility endpoints for health checks 
and listing all registered routes.

Modules:
    - app.memory: Handles memory-related operations.
    - app.buffer: Manages buffering operations.
    - app.status: Provides status-related endpoints.
    - app.scheduler: Manages scheduling tasks.
    - app.docs: Handles API documentation.
    - app.message.message: Processes general message-related operations.
    - app.message.multiturn: Handles multi-turn message processing.
    - app.message.singleturn: Handles single-turn message processing.
    - app.models: Manages model-related operations.

Routes:
    - /ping: Health check endpoint to verify the service status.
    - /__list_routes__: Utility endpoint to list all registered API routes.

Usage:
    Import this module and run the FastAPI application to start the service.
"""

from app.memory import router as memory_router
from app.buffer import router as buffer_router
from app.status import router as status_router
from app.scheduler import router as scheduler_router
from app.docs import router as docs_router
from app.message.message import router as message_router
from app.message.multiturn import router as message_multiturn_router
from app.message.singleturn import router as message_singleturn_router
from app.models import router as models_router

from fastapi import FastAPI
from fastapi.routing import APIRoute
app = FastAPI()
app.include_router(memory_router, tags=["memory"])
app.include_router(buffer_router, tags=["buffer"])
app.include_router(status_router, tags=["status"])
app.include_router(scheduler_router, tags=["scheduler"])
app.include_router(docs_router, tags=["docs"])
app.include_router(message_router, prefix="/message", tags=["message"])
app.include_router(message_multiturn_router, tags=["message"])
app.include_router(message_singleturn_router, tags=["message"])
app.include_router(models_router, tags=["models"])


@app.get("/ping")
def ping():
    """
    Health check endpoint that returns the service status.

    Returns:
        Dict[str, str]: A dictionary with a 'status' key indicating the service is operational.
    """
    return {"status": "ok"}


@app.get("/__list_routes__")
def list_routes():
    """
    Endpoint to list all registered API routes in the application.

    Returns:
        List[Dict[str, Union[str, List[str]]]]: A list of dictionaries containing route paths and their supported HTTP methods.
    """
    return [
        {"path": route.path, "methods": list(route.methods)}
        for route in app.routes
        if isinstance(route, APIRoute)
    ]
