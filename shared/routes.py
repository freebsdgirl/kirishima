"""
This module defines API routes for the application using FastAPI's APIRouter.

Routes:
    - `/ping`: A health check endpoint to verify the service status.
    - `/__list_routes__`: An endpoint to list all registered API routes in the application.

Modules:
    - fastapi.APIRouter: Used to create and manage API routes.
    - fastapi.routing.APIRoute: Used to inspect and list route details.

Functions:
    - ping(): Returns the service status as a dictionary with a 'status' key.
    - list_routes(): Returns a list of dictionaries containing route paths and their supported HTTP methods.

"""


from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute


router = APIRouter()


@router.get("/ping")
def ping():
    """
    Health check endpoint that returns the service status.

    Returns:
        Dict[str, str]: A dictionary with a 'status' key indicating the service is operational.
    """
    return {"status": "ok"}


def register_list_routes(app: FastAPI):
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
