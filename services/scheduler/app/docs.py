"""
This module defines the API documentation for the scheduler service.

It provides an endpoint to export the service's metadata, including its
version, port, and available API endpoints with their descriptions, input,
and output specifications.

Functions:
    - get_git_revision(): Retrieves the current Git revision hash of the
      repository. Returns "unknown" if the revision cannot be determined.

Routes:
    - GET /export: Exports the service metadata, including:
        - Service name and port
        - Current Git revision
        - List of available endpoints with their details:
            - /jobs (POST): Schedule a new job with 'date' or 'interval' triggers.
            - /jobs (GET): List all scheduled jobs.
            - /jobs/{job_id} (DELETE): Remove a job by its ID.
            - /jobs/{job_id}/pause (POST): Pause a running job.
            - /jobs/{job_id}/resume (POST): Resume a paused job.
"""

from fastapi import APIRouter
import subprocess
import os


service_port = os.getenv('SERVICE_PORT', '4201')

router = APIRouter()

def get_git_revision():
    try:
        return subprocess.check_output(
            ["git", "-C", ".", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
    except Exception:
        return "unknown"

@router.get("/export")
def export_docs():
    return {
        "service": "scheduler",
        "port": service_port,
        "version": get_git_revision(),
        "endpoints": [
            {
                "path": "/jobs",
                "method": "POST",
                "description": "Schedule a new job. Supports 'date' or 'interval' triggers.",
                "input": {
                    "external_url": "string (required)",
                    "trigger": "'date' or 'interval'",
                    "run_date": "datetime (required for 'date')",
                    "interval_minutes": "int (required for 'interval')",
                    "metadata": "dict (optional)"
                },
                "output": {
                    "job_id": "string",
                    "next_run_time": "datetime",
                    "trigger": "string",
                    "metadata": "dict"
                }
            },
            {
                "path": "/jobs",
                "method": "GET",
                "description": "List all scheduled jobs, including metadata and next run times."
            },
            {
                "path": "/jobs/{job_id}",
                "method": "DELETE",
                "description": "Remove a job from the scheduler by ID.",
                "output": {
                    "status": "success",
                    "message": "string"
                }
            },
            {
                "path": "/jobs/{job_id}/pause",
                "method": "POST",
                "description": "Pause a running job.",
                "output": {
                    "status": "success",
                    "message": "string"
                }
            },
            {
                "path": "/jobs/{job_id}/resume",
                "method": "POST",
                "description": "Resume a paused job.",
                "output": {
                    "status": "success",
                    "message": "string"
                }
            }
        ]
    }
