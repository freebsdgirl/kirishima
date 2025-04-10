"""
This module defines an API router for exporting documentation about the service's endpoints
and metadata. It includes functionality to retrieve the current Git commit hash for versioning
purposes and provides a structured JSON representation of the API's configuration.
Functions:
    get_git_revision():
        Retrieves the current Git repository's HEAD commit hash. Returns "unknown" if the
        Git command fails.
    export_docs():
        Exports API documentation, including service metadata, version information, and
        details about available endpoints.
Routes:
    GET /docs/export:
        Returns a JSON object containing the service's metadata and endpoint documentation.
"""
from fastapi import APIRouter
router = APIRouter()

import subprocess
import os

service_port = os.getenv("SERVICE_PORT", 4200)


def get_git_revision():
    """
    Retrieves the current Git repository's HEAD commit hash.
    
    Returns the full SHA-1 hash of the current HEAD commit. If the Git command fails,
    returns "unknown" to prevent breaking the application.
    
    Returns:
        str: The current Git commit hash or "unknown" if retrieval fails.
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
    Export API documentation for the service, including version, endpoints, and their details.

    Returns a comprehensive JSON representation of the API's current configuration,
    including service metadata, available endpoints, and their input/output specifications.

    Returns:
        dict: A structured dictionary containing service and endpoint documentation.
    """
    return {
        "service": "api-intermediary",
        "port": service_port,
        "version": get_git_revision(),
        "endpoints": [
            {
                "path": "/models/{model_id}",
                "method": "GET",
                "description": "Returns model metadata and fine-tuning details for a specific model ID."
            },
            {
                "path": "/models",
                "method": "GET",
                "description": "Lists all available models from the backend provider (e.g. Ollama)."
            },
            {
                "path": "/completions",
                "method": "POST",
                "description": "Submits a single-turn text prompt and returns a plain text response using the default model.",
                "input": {
                    "prompt": "string (required)",
                    "temperature": "float (optional)",
                    "top_p": "float (optional)",
                    "max_tokens": "int (optional)"
                },
                "output": {
                    "text": "string",
                    "model": "string",
                    "id": "string"
                }
            },
            {
                "path": "/chat/completions",
                "method": "POST",
                "description": "Handles a multi-turn OpenAI-style chat request, applying memory, context, and retry logic.",
                "input": {
                    "messages": "list of {role: string, content: string}",
                    "model": "string (optional)",
                    "temperature": "float (optional)",
                    "top_p": "float (optional)",
                    "stream": "bool (optional)"
                },
                "output": {
                    "choices": "list of response messages",
                    "model": "string",
                    "id": "string"
                }
            },
            {
                "path": "/v1/chat/completions",
                "method": "POST",
                "description": "Alias for /chat/completions, provided for compatibility with VS Code extensions and clients.",
                "input": {
                    "messages": "list of {role: string, content: string}",
                    "model": "string (optional)",
                    "temperature": "float (optional)",
                    "top_p": "float (optional)",
                    "stream": "bool (optional)"
                },
                "output": {
                    "choices": "list of response messages",
                    "model": "string",
                    "id": "string"
                }
            }
        ]
    }
