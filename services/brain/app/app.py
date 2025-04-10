"""
This module defines the main FastAPI application and includes various routers for different functionalities.

Routers:
    - memory_router: Handles memory-related operations.
    - buffer_router: Manages buffer-related operations.
    - status_router: Provides service status endpoints.
    - scheduler_router: Manages scheduling tasks.
    - docs_router: Handles API documentation endpoints.
    - message_router: Manages message-related operations, with a prefix "/message" and tag "message".

Endpoints:
    - /ping: Health check endpoint to verify the service is operational.
    - /__list_routes__: Lists all registered API routes in the application, including their paths and supported HTTP methods.

Attributes:
    app (FastAPI): The main FastAPI application instance.
"""

from app.memory import router as memory_router
from app.buffer import router as buffer_router
from app.status import router as status_router
from app.scheduler import router as scheduler_router
from app.docs import router as docs_router
from app.message.message import router as message_router
from app.message.multiturn import router as message_multiturn_router
from app.message.singleturn import router as message_singleturn_router

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
