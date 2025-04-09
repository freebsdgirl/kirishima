"""
This module defines the FastAPI router for exporting documentation of the "contacts" service.

Functions:
    get_git_revision():
        Retrieves the current Git revision hash of the repository. If the hash cannot be determined,
        it returns "unknown".

    export_docs():
        Endpoint: GET /docs/export
        Returns a JSON object containing:
            - Service name ("contacts")
            - Port number (4202)
            - Current Git version hash
            - List of API endpoints with their details, including:
                - Path
                - HTTP method
                - Description
                - Input and output schemas
"""
from fastapi import APIRouter
import subprocess
import os


service_port = os.getenv('SERVICE_PORT', '4202')

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
    return {
        "service": "contacts",
        "port": service_port,
        "version": get_git_revision(),
        "endpoints": [
            {
                "path": "/contact",
                "method": "POST",
                "description": "Create a new contact with aliases, fields, and optional notes.",
                "input": {
                    "aliases": "list of strings",
                    "fields": "list of {key: string, value: string}",
                    "notes": "string (optional)"
                },
                "output": {
                    "id": "string",
                    "status": "created"
                }
            },
            {
                "path": "/contacts",
                "method": "GET",
                "description": "List all contacts with full details: aliases, fields, and notes.",
                "output": [
                    {
                        "id": "string",
                        "aliases": "list of strings",
                        "fields": "list of {key: string, value: string}",
                        "notes": "string"
                    }
                ]
            },
            {
                "path": "/contact/{contact_id}",
                "method": "PUT",
                "description": "Replace an existing contact with new data, including aliases and fields.",
                "input": {
                    "aliases": "list of strings",
                    "fields": "list of {key: string, value: string}",
                    "notes": "string (optional)"
                },
                "output": {
                    "id": "string",
                    "status": "replaced"
                }
            },
            {
                "path": "/contact/{contact_id}",
                "method": "PATCH",
                "description": "Partially update a contact (e.g., add aliases or fields, or update notes).",
                "input": {
                    "aliases": "list of strings (optional)",
                    "fields": "list of {key: string, value: string} (optional)",
                    "notes": "string (optional)"
                },
                "output": {
                    "id": "string",
                    "status": "patched"
                }
            },
            {
                "path": "/contact/{contact_id}",
                "method": "DELETE",
                "description": "Delete a contact and all associated aliases and fields.",
                "output": {
                    "id": "string",
                    "status": "deleted"
                }
            },
            {
                "path": "/search",
                "method": "GET",
                "description": "Search contacts by alias or field value. Returns matches with full contact details.",
                "input": {
                    "q": "string (query param)"
                },
                "output": [
                    {
                        "id": "string",
                        "aliases": "list of strings",
                        "fields": "list of {key: string, value: string}",
                        "notes": "string"
                    }
                ]
            }
        ]
    }
