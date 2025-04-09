"""
This module defines the API documentation export functionality for the iMessage service.

The module includes:
- A FastAPI router for defining API routes.
- A utility function to retrieve the current Git revision of the codebase.
- An endpoint to export structured API documentation, including service metadata and available routes.

Functions:
    - get_git_revision(): Retrieves the current Git commit hash of the repository.
    - export_docs(): Returns a dictionary containing metadata about the service and its API endpoints.

Routes:
    - GET /export: Exports the API documentation for the service.

Environment Variables:
    - SERVICE_PORT: The port on which the service is running. Defaults to '4204' if not set.
"""

from fastapi import APIRouter
import subprocess
import os

service_port = os.getenv('SERVICE_PORT', '4204')


router = APIRouter()


def get_git_revision():
    try:
        return subprocess.check_output(
            ["git", "-C", ".", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
    except Exception:
        return "unknown"


@router.get("/docs/export")
def export_docs():
    """
    Export the API documentation for this service, including endpoint routes and descriptions.

    Returns:
        dict: A structured dictionary representing the API's available routes and their purposes.
    """
    return {
        "service": "imessage",
        "port": service_port,
        "version": get_git_revision(),
        "endpoints": [
            {
                "method": "GET",
                "path": "/ping",
                "description": "Health check endpoint that returns a simple status response."
            },
            {
                "method": "POST",
                "path": "/imessage/send",
                "description": "Send an iMessage to a specified recipient via BlueBubbles server."
            },
            {
                "method": "POST",
                "path": "/imessage/recv",
                "description": "Receive an incoming iMessage webhook payload from BlueBubbles."
            }
        ]
    }