"""
This module defines the main FastAPI application and includes various API routers for different functionalities.

Modules:
    - app.v1.chat.completions: Handles chat completion-related endpoints.
    - app.v1.completions: Handles general completion-related endpoints.
    - app.v1.embeddings: Handles embedding-related endpoints.
    - app.v1.models.get_model: Handles fetching details of a specific model.
    - app.v1.models.list_models: Handles listing all available models.
    - app.docs: Handles API documentation endpoints.

Routes:
    - /ping: Health check endpoint to verify the service status.
    - /__list_routes__: Endpoint to list all registered API routes in the application.

Attributes:
    app (FastAPI): The main FastAPI application instance.

Functions:
    - ping(): Health check endpoint that returns the service status.
    - list_routes(): Lists all registered API routes in the application.
"""

from app.v1.chat.completions import router as chat_router
from app.v1.completions import router as completions_router
from app.v1.embeddings import router as embeddings_router
from app.v1.models.get_model import router as get_model_router
from app.v1.models.list_models import router as list_models_router
from app.docs import router as docs_router


from fastapi import FastAPI
from fastapi.routing import APIRoute
app = FastAPI()
app.include_router(chat_router, tags=["chat"])
app.include_router(completions_router, tags=["completions"])
app.include_router(embeddings_router, tags=["embeddings"])
app.include_router(get_model_router, tags=["get_model"])
app.include_router(list_models_router, tags=["list_models"])
app.include_router(docs_router, tags=["docs"])


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
