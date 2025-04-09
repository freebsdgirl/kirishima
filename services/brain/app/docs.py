"""
This module defines the FastAPI router for the "brain" service and provides an endpoint
to export documentation for the service's API.
Functions:
    get_git_revision():
        Retrieves the current Git commit hash of the repository.
    export_docs():
        Exports the API documentation, including service metadata, version, and
        details of all available endpoints.
Endpoints:
    - /docs/export (GET):
        Exports the API documentation for the service.
    - /buffer/conversation (POST):
        Inserts a conversation entry into the rolling buffer database.
    - /buffer/conversation (GET):
        Retrieves all conversation summaries from the rolling buffer database.
    - /memory (POST):
        Adds a new memory with embeddings to the memory storage service.
    - /memory/search/id (POST):
        Searches for a memory's ID based on input text.
    - /memory (GET):
        Lists memories by component.
    - /memory/{id} (GET):
        Retrieves a specific memory by ID.
    - /memory/{id} (DELETE):
        Deletes a memory by ID.
    - /memory/{id} (PUT):
        Replaces a memory by ID with full new data.
    - /memory/{id} (PATCH):
        Partially updates a memory by ID.
    - /status/mode (GET):
        Retrieves the current system mode from the status database.
    - /status/mode/{mode} (POST):
        Sets the current system mode in the status database.
    - /scheduler/job (POST):
        Adds a new job to the external scheduler service.
    - /scheduler/job (GET):
        Lists all scheduled jobs from the external scheduler service.
    - /scheduler/job/{job_id} (DELETE):
        Deletes a job from the external scheduler service by job ID.
    - /scheduler/callback (POST):
        Callback endpoint triggered by the scheduler to execute a specified function.
"""

from fastapi import APIRouter
router = APIRouter()

import subprocess

import os
service_port = os.getenv("SERVICE_PORT", 4207)


def get_git_revision():
    """
    Retrieve the current Git commit hash of the repository.
    
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
        "service": "brain",
        "port": service_port,
        "version": get_git_revision(),
        "endpoints": [
            {
                "path": "/buffer/conversation",
                "method": "POST",
                "description": "Insert a conversation entry into the rolling buffer database.",
                "input": {
                    "sender": "string",
                    "content": "string",
                    "timestamp": "string (ISO 8601)",
                    "platform": "string",
                    "mode": "string"
                },
                "output": {
                    "status": "string",
                    "message": "string"
                }
            },
            {
                "path": "/buffer/conversation",
                "method": "GET",
                "description": "Retrieve all conversation summaries from the rolling buffer database.",
                "output": [
                    {
                        "summary": "string",
                        "timestamp": "string"
                    }
                ]
            },
            {
                "path": "/memory",
                "method": "POST",
                "description": "Add a new memory with embeddings to the memory storage service.",
                "input": {
                    "memory": "string",
                    "component": "string",
                    "priority": "float"
                }
            },
            {
                "path": "/memory/search/id",
                "method": "POST",
                "description": "Search for a memory's ID based on input text.",
                "input": {
                    "input": "string"
                },
                "output": {
                    "id": "string"
                }
            },
            {
                "path": "/memory",
                "method": "GET",
                "description": "List memories by component.",
                "input": {
                    "component": "string",
                    "limit": "int (optional, default: 5)"
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
                "description": "Replace a memory by ID with full new data.",
                "input": {
                    "memory": "string",
                    "component": "string",
                    "priority": "float"
                }
            },
            {
                "path": "/memory/{id}",
                "method": "PATCH",
                "description": "Partially update a memory by ID.",
                "input": {
                    "memory": "string (optional)",
                    "component": "string (optional)",
                    "priority": "float (optional)"
                }
            },
            {
                "path": "/status/mode",
                "method": "GET",
                "description": "Retrieve the current system mode from the status database."
            },
            {
                "path": "/status/mode/{mode}",
                "method": "POST",
                "description": "Set the current system mode in the status database."
            },
            {
                "path": "/scheduler/job",
                "method": "POST",
                "description": "Add a new job to the external scheduler service.",
                "input": {
                    "id": "string",
                    "external_url": "string",
                    "trigger": "'date' or 'interval'",
                    "run_date": "string (optional)",
                    "interval_minutes": "int (optional)",
                    "metadata": "dict (optional)"
                }
            },
            {
                "path": "/scheduler/job",
                "method": "GET",
                "description": "List all scheduled jobs from the external scheduler service."
            },
            {
                "path": "/scheduler/job/{job_id}",
                "method": "DELETE",
                "description": "Delete a job from the external scheduler service by job ID."
            },
            {
                "path": "/scheduler/callback",
                "method": "POST",
                "description": "Callback endpoint triggered by the scheduler. Executes the function specified in metadata.",
                "input": {
                    "metadata": "dict including 'function'",
                    "executed_at": "string (ISO 8601)"
                }
            }
        ]
    }
