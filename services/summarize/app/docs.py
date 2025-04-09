"""
This module defines the FastAPI router for the "summarize" service, providing
endpoints for managing buffers, summaries, and exporting service documentation.

Functions:
    - get_git_revision: Retrieves the current Git revision hash of the repository.
    - export_docs: Exports metadata about the service, including available endpoints.

Endpoints:
    - /context/{user_id} [GET]: Returns all buffer entries and summaries for a user.
    - /summarize_buffers [POST]: Summarizes all current buffers across users, stores results, and deletes processed buffers.
    - /buffer [POST]: Adds a new buffer entry for a user.
    - /buffer [GET]: Lists all buffer entries across all users.
    - /buffer/{user_id} [GET]: Lists all buffer entries for a specific user.
    - /buffer/{user_id} [DELETE]: Deletes all buffer entries for a user.
    - /summary [POST]: Adds a new summary entry with metadata.
    - /summary/{id} [GET]: Retrieves a summary entry by ID.
    - /summary/{id} [DELETE]: Deletes a specific summary by ID.
    - /summary/user/{user_id} [GET]: Lists all summaries for a user.
    - /summary/user/{user_id} [DELETE]: Deletes all summaries for a user.
    - /summary/search [GET]: Searches for summaries matching a query.

Environment Variables:
    - SERVICE_PORT: The port on which the service is running (default: 4203).
"""

import subprocess

import os
service_port = os.getenv('SERVICE_PORT', '4203')


from fastapi import APIRouter
router = APIRouter()


def get_git_revision():
    """
    Retrieves the current Git revision hash of the repository.
    
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


@router.get("/docs/export")
def export_docs():
    return {
        "service": "summarize",
        "port": service_port,
        "version": get_git_revision(),
        "endpoints": [

            # === CONTEXT ===
            {
                "path": "/context/{user_id}",
                "method": "GET",
                "description": "Returns all buffer entries and summaries for a user.",
                "output": {
                    "buffers": "list of buffer entries",
                    "summaries": "list of summaries"
                }
            },
            {
                "path": "/summarize_buffers",
                "method": "POST",
                "description": "Summarize all current buffers across users, store results, and delete processed buffers.",
                "output": {
                    "user_id": {
                        "summary_id": "string",
                        "deleted": "int"
                    }
                }
            },

            # === BUFFER ===
            {
                "path": "/buffer",
                "method": "POST",
                "description": "Add a new buffer entry for a user.",
                "input": {
                    "text": "string",
                    "source": "'User' or 'Kirishima'",
                    "user_id": "string",
                    "platform": "string",
                    "timestamp": "ISO 8601"
                },
                "output": {
                    "status": "success",
                    "id": "string"
                }
            },
            {
                "path": "/buffer",
                "method": "GET",
                "description": "List all buffer entries across all users."
            },
            {
                "path": "/buffer/{user_id}",
                "method": "GET",
                "description": "List all buffer entries for a specific user."
            },
            {
                "path": "/buffer/{user_id}",
                "method": "DELETE",
                "description": "Delete all buffer entries for a user.",
                "output": {
                    "status": "success",
                    "deleted": "int"
                }
            },

            # === SUMMARY ===
            {
                "path": "/summary",
                "method": "POST",
                "description": "Add a new summary entry with metadata.",
                "input": {
                    "text": "string",
                    "platform": "string",
                    "user_id": "string",
                    "timestamp": "datetime (optional)",
                    "save": "bool (default true)"
                },
                "output": {
                    "status": "success",
                    "id": "string"
                }
            },
            {
                "path": "/summary/{id}",
                "method": "GET",
                "description": "Retrieve a summary entry by ID."
            },
            {
                "path": "/summary/{id}",
                "method": "DELETE",
                "description": "Delete a specific summary by ID."
            },
            {
                "path": "/summary/user/{user_id}",
                "method": "GET",
                "description": "List all summaries for a user."
            },
            {
                "path": "/summary/user/{user_id}",
                "method": "DELETE",
                "description": "Delete all summaries for a user."
            },
            {
                "path": "/summary/search",
                "method": "GET",
                "description": "Search for summaries matching a query.",
                "input": {
                    "q": "string (query param)"
                }
            }
        ]
    }
