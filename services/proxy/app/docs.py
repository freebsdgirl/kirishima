"""
This module defines the API routes and utility functions for the Proxy service.
Modules:
    subprocess: Provides access to spawn new processes, connect to their input/output/error pipes, and obtain their return codes.
    os: Provides a way of using operating system-dependent functionality.
    fastapi.APIRouter: Used to create route groups for the FastAPI application.
Functions:
    get_git_revision():
    export_docs():
Routes:
    GET /export:
        Provides metadata about the service, including its version and available endpoints.
"""

import subprocess
import os
service_port = os.getenv('SERVICE_PORT', '4205')


from fastapi import APIRouter
router = APIRouter()


def get_git_revision():
    """
    Retrieve the current Git repository's HEAD commit hash.
    
    Returns:
        str: The full commit hash of the current HEAD, or "unknown" if retrieval fails.
    """
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
    Export the API documentation for the Proxy service.

    Returns:
        dict: Structured endpoint definitions for LLM-safe access.
    """
    return {
        "service": "proxy",
        "port": service_port,
        "version": get_git_revision(),
        "endpoints": [
            {
                "method": "POST",
                "path": "/from/imessage",
                "description": "Generate a reply for an iMessage using a prompt builder and local LLM."
            }
        ]
    }