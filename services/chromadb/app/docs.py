"""
This module defines the FastAPI router for the ChromaDB service and provides an endpoint
to export documentation for the service's API. It includes functionality to retrieve the
current Git commit hash and defines a set of endpoints for managing memory, summaries, 
and buffer entries.
Functions:
    get_git_revision():
        Retrieves the current Git commit hash for the project.
Routes:
    /export (GET):
        Exports the API documentation, including service metadata, version, and endpoint details.
Endpoint Categories:
    - MEMORY:
        Endpoints for managing memory collections, including adding, retrieving, updating, 
        and deleting memory entries.
    - SUMMARIZE:
        Endpoints for storing and retrieving summary documents with metadata, as well as 
        performing semantic searches.
    - BUFFER:
        Endpoints for managing short-form messages in a user's buffer, including adding, 
        retrieving, and deleting buffer entries.
"""

import subprocess

import os
service_port = os.getenv('SERVICE_PORT', '4206')

from fastapi import APIRouter
router = APIRouter()


def get_git_revision() -> str:
    """
    Retrieve the current Git commit hash for the project.
    
    Returns:
        str: The Git commit hash of the current HEAD, or "unknown" if retrieval fails.
    """
    try:
        return subprocess.check_output(
            ["git", "-C", ".", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
    except Exception:
        return "unknown"


@router.get("/export", response_model=dict)
def export_docs() -> dict:
    return {
        "service": "chroma",
        "port": service_port,
        "version": get_git_revision(),
        "endpoints": [

            # === MEMORY ===
            {
                "path": "/memory/search/id",
                "method": "POST",
                "description": "Search memory collection for the first document containing input text. Returns matching ID.",
                "input": {"input": "string"}
            },
            {
                "path": "/memory",
                "method": "POST",
                "description": "Add a new memory with embedding, priority, timestamp, and component metadata.",
                "input": {
                    "memory": "string",
                    "component": "string",
                    "priority": "float",
                    "embedding": "list of floats"
                },
                "output": {
                    "id": "string",
                    "timestamp": "ISO 8601 string"
                }
            },
            {
                "path": "/memory",
                "method": "GET",
                "description": "List recent memories for a given component. Sorted by timestamp descending.",
                "input": {
                    "component": "string (query param)",
                    "limit": "int (query param)"
                }
            },
            {
                "path": "/memory/{id}",
                "method": "GET",
                "description": "Retrieve a specific memory by ID."
            },
            {
                "path": "/memory/{id}",
                "method": "DELETE",
                "description": "Delete a memory by ID."
            },
            {
                "path": "/memory/{id}",
                "method": "PUT",
                "description": "Replace an existing memory with new data.",
                "input": {
                    "memory": "string",
                    "component": "string",
                    "priority": "float",
                    "embedding": "list of floats"
                }
            },
            {
                "path": "/memory/{id}",
                "method": "PATCH",
                "description": "Partially update an existing memory.",
                "input": {
                    "memory": "string (optional)",
                    "component": "string (optional)",
                    "priority": "float (optional)",
                    "embedding": "list of floats (optional)"
                }
            },

            # === SUMMARIZE ===
            {
                "path": "/summarize",
                "method": "POST",
                "description": "Store a summary document with embedding and metadata (user ID, platform, timestamp).",
                "input": {
                    "text": "string",
                    "platform": "string",
                    "user_id": "string",
                    "timestamp": "datetime (optional)",
                    "save": "bool (default true)"
                }
            },
            {
                "path": "/summarize/{id}",
                "method": "GET",
                "description": "Retrieve a stored summary by ID."
            },
            {
                "path": "/summarize/user/{user_id}",
                "method": "GET",
                "description": "List summaries for a specific user with optional filters.",
                "input": {
                    "since": "datetime (optional)",
                    "platform": "string (optional)"
                }
            },
            {
                "path": "/summarize/{id}",
                "method": "DELETE",
                "description": "Delete a summary by ID."
            },
            {
                "path": "/summarize/search",
                "method": "GET",
                "description": "Semantic search for summaries with scoring based on meaning and recency.",
                "input": {
                    "q": "string (query param)",
                    "user_id": "string (optional)",
                    "platform": "string (optional)",
                    "since": "datetime (optional)"
                }
            },

            # === BUFFER ===
            {
                "path": "/buffer",
                "method": "POST",
                "description": "Add a short-form message to a user's buffer (text + user/platform/timestamp).",
                "input": {
                    "text": "string",
                    "user_id": "string",
                    "platform": "string",
                    "timestamp": "datetime (optional)"
                },
                "output": {
                    "id": "string",
                    "status": "success"
                }
            },
            {
                "path": "/buffer",
                "method": "GET",
                "description": "Get all buffer entries (across all users)."
            },
            {
                "path": "/buffer/{user_id}",
                "method": "GET",
                "description": "Get buffer entries for a specific user."
            },
            {
                "path": "/buffer/{user_id}",
                "method": "DELETE",
                "description": "Delete all buffer entries for a user."
            }
        ]
    }
