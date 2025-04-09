"""
Scheduler module for managing job scheduling via an external scheduler service.

This module provides FastAPI routes for interacting with a job scheduler, allowing
creation, listing, and deletion of scheduled jobs. It uses configuration from a 
config module and handles communication with an external scheduler URL.

Key features:
- Add new jobs with configurable scheduling parameters
- Supports date-based and interval-based job scheduling
- Robust error handling for scheduler service interactions
"""
import app.config

from shared.models.scheduler import SchedulerJobRequest

from pydantic import BaseModel
from typing import Dict, Any

from shared.log_config import get_logger

logger = get_logger(__name__)

import requests

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

import os
scheduler_host = os.getenv("SCHEDULER_HOST", "localhost")
scheduler_port = os.getenv("SCHEDULER_PORT", "4201")
scheduler_url = f"http://{scheduler_host}:{scheduler_port}"


class SchedulerCallbackRequest(BaseModel):
    """
    Represents a request payload for a scheduler callback with metadata and execution timestamp.
    
    Attributes:
        metadata (Dict[str, Any]): A dictionary containing arbitrary metadata associated with the scheduled job.
        executed_at (str): An ISO 8601 formatted timestamp indicating when the job was executed.
    """
    metadata: Dict[str, Any]
    executed_at: str  # ISO timestamp


@router.post("/scheduler/callback", response_model=dict)
def scheduler_callback(payload: SchedulerCallbackRequest) -> dict:
    """
    Handle a scheduler callback by executing a specified function from global namespace.

    Expects a payload with metadata containing a 'function' key. Retrieves and calls
    the specified function, returning a success status or raising an appropriate
    HTTPException for missing or invalid functions.

    Args:
        payload (SchedulerCallbackRequest): Callback request with job metadata.

    Returns:
        dict: A success status with the executed function name.

    Raises:
        HTTPException: 400 if function metadata is missing,
                    404 if function is not found,
                    500 if function execution fails.
    """
    logger.debug(f"Received scheduler callback: {payload}")

    metadata = payload.metadata
    func_name = metadata.get("function")

    if not func_name:
        logger.error("Missing 'function' in metadata")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'function' in metadata"
        )

    try:
        func = globals()[func_name]

    except KeyError:
        logger.error(f"Function '{func_name}' not found in globals.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Function '{func_name}' not found"
        )

    try:
        func()
        logger.info(f"Function '{func_name}' executed successfully.")
        return {
            "status": "success",
            "function": func_name
        }

    except Exception as e:
        logger.error(f"Function execution failed: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Function execution failed: {str(e)}"
        )


@router.post("/scheduler/job", response_model=dict)
def scheduler_add_job(request: SchedulerJobRequest) -> dict:
    """
    Add a new job to the scheduler service.

    Sends a job scheduling request to the configured scheduler URL. Handles potential
    connection and HTTP errors by raising appropriate HTTPExceptions.

    Args:
        request (SchedulerJobRequest): Details of the job to be scheduled.

    Returns:
        dict: The response from the scheduler service containing job details.

    Raises:
        HTTPException: If the scheduler service is unreachable or returns an error.
    """

    logger.debug(f"Adding job: {request}")

    try:
        response = requests.post(f"{scheduler_url}/jobs", json=request.dict())
        response.raise_for_status()
        logger.info(f"Job added successfully: {response.json()}")
        return response.json()

    except requests.exceptions.HTTPError as e:
        logger.error(f"Scheduler error: {response.status_code} - {response.text}")
        status_code=e.response.status_code
        detail=e.response.text or str(e)

        # Custom interpretation
        if status_code == status.HTTP_409_CONFLICT:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail
            )

        elif status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail
            )

        else:
            raise HTTPException(
                status_code,
                detail
            )
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Scheduler unreachable: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Scheduler unreachable: {str(e)}"
        )


@router.get("/scheduler/job", response_model=list)
def scheduler_list_jobs():
    logger.debug(f"Listing jobs")

    try:
        response = requests.get(f"{scheduler_url}/jobs")
        response.raise_for_status()

        logger.info(f"Jobs listed successfully: {response.json()}")

        return response.json()

    except requests.exceptions.HTTPError as e:
        logger.error(f"Scheduler error: {response.status_code} - {response.text}")

        status_code=e.response.status_code
        detail=e.response.text or str(e)

        raise HTTPException(
            status_code,
            detail
        )
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Scheduler unreachable: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Scheduler unreachable: {str(e)}"
        )


@router.delete("/scheduler/job/{job_id}", response_model=dict)
def scheduler_delete_job(job_id: str) -> dict:
    """
    Delete a scheduled job by its job ID.

    Args:
        job_id (str): The unique identifier of the job to be deleted.

    Returns:
        Dict[str, str]: A dictionary with status and job_id confirming successful deletion.

    Raises:
        HTTPException: If there is an error communicating with the scheduler service,
        with appropriate status codes for HTTP errors or service unavailability.
    """
    logger.debug(f"Deleting job: {job_id}")

    try:
        response = requests.delete(f"{scheduler_url}/jobs/{job_id}")
        response.raise_for_status()

        return {
            "status": "success",
            "job_id": job_id
        }

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        detail = e.response.text or str(e)

        logger.error(f"Scheduler error: {status_code} - {detail}")

        raise HTTPException(status_code, detail)

    except requests.exceptions.RequestException as e:
        logger.error(f"Scheduler unreachable: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Scheduler unreachable: {str(e)}"
        )