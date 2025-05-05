"""
This module provides FastAPI endpoints for interacting with a scheduler service.

Endpoints:
    - POST /scheduler/callback: Handles scheduler callbacks by executing specified functions.
    - POST /scheduler/job: Adds a new job to the scheduler service.
    - GET /scheduler/job: Retrieves a list of all scheduled jobs.
    - DELETE /scheduler/job/{job_id}: Deletes a scheduled job by its job ID.

The module communicates with the scheduler service via HTTP requests, using service discovery
to obtain the scheduler's address and port. It handles connection errors and HTTP errors,
logging relevant information and raising appropriate HTTPExceptions for FastAPI responses.

Dependencies:
    - shared.models.scheduler: SchedulerJobRequest, JobResponse, SchedulerCallbackRequest
    - shared.consul: Service discovery for scheduler address/port
    - shared.log_config: Logging configuration
    - httpx: Asynchronous HTTP client
    - fastapi: API routing and exception handling
    - shared.config: Configuration for TIMEOUT
    - app.scheduler.job_summarize: Function to summarize user buffers
"""
from shared.config import TIMEOUT
import shared.consul

from shared.models.scheduler import SchedulerJobRequest, SchedulerCallbackRequest

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx
import inspect

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

# global functions to be called by scheduler
from app.scheduler.job_summarize import (
    summarize_user_buffer_morning,
    summarize_user_buffer_afternoon,
    summarize_user_buffer_evening,
    summarize_user_buffer_night
)

from app.scheduler.job_notification import check_notifications

globals()["check_notifications"]                = check_notifications
globals()["summarize_user_buffer_morning"]      = summarize_user_buffer_morning
globals()["summarize_user_buffer_afternoon"]    = summarize_user_buffer_afternoon
globals()["summarize_user_buffer_evening"]      = summarize_user_buffer_evening
globals()["summarize_user_buffer_night"]        = summarize_user_buffer_night


@router.post("/scheduler/callback", response_model=dict)
async def scheduler_callback(payload: SchedulerCallbackRequest) -> dict:
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

    logger.debug(f"POST /scheduler/callback Request: {payload}")

    metadata = payload.metadata
    func_name = metadata.get("function")

    if not func_name:
        logger.error(f"Missing 'function' in metadata: {payload}")

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
        logger.info(f"Executing function: {func_name}")
        if inspect.iscoroutinefunction(func):
            await func()
        else:
            func()

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
async def scheduler_add_job(request: SchedulerJobRequest) -> dict:
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
    logger.debug(f"POST /scheduler/job Request: {request}")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            scheduler_address, scheduler_port = shared.consul.get_service_address('scheduler')
            if not scheduler_address or not scheduler_port:
                logger.error("scheduler service address or port is not available.")

                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="scheduler service is unavailable."
                )

            response = await client.post(f"http://{scheduler_address}:{scheduler_port}/jobs", json=request.model_dump())
            response.raise_for_status()

            logger.info(f"Job added successfully: {response.json()}")
            return response.json()

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from scheduler service: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error forwarding to scheduler service: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error forwarding to scheduler service: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )
        
        except Exception as e:
            logger.error(f"Unexpected error in scheduler service: {e}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error in scheduler service: {e}"
            )


@router.get("/scheduler/job", response_model=list)
async def scheduler_list_jobs():
    """
    Retrieve a list of all scheduled jobs from the scheduler service.

    Sends a GET request to the configured scheduler URL to fetch all jobs.
    Handles potential connection and HTTP errors by raising appropriate HTTPExceptions.

    Returns:
        list: A list of scheduled jobs from the scheduler service.

    Raises:
        HTTPException: If the scheduler service is unreachable or returns an error.
    """
    logger.debug(f"GET /scheduler/job Request")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            scheduler_address, scheduler_port = shared.consul.get_service_address('scheduler')
            if not scheduler_address or not scheduler_port:
                logger.error("scheduler service address or port is not available.")

                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="scheduler service is unavailable."
                )

            response = await client.get(f"http://{scheduler_address}:{scheduler_port}/jobs")
            response.raise_for_status()

            return response.json()

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from scheduler service: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error forwarding to scheduler service: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error forwarding to scheduler service: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )


@router.delete("/scheduler/job/{job_id}", response_model=dict)
async def scheduler_delete_job(job_id: str) -> dict:
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
    logger.debug(f"DELETE /scheduler/job/{job_id} Request")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            scheduler_address, scheduler_port = shared.consul.get_service_address('scheduler')
            if not scheduler_address or not scheduler_port:
                logger.error("scheduler service address or port is not available.")

                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="scheduler service is unavailable."
                )

            response = await client.delete(f"http://{scheduler_address}:{scheduler_port}/jobs/{job_id}")
            response.raise_for_status()

            logger.info(f"Job deleted successfully: {response.json()}")

            return {
                "status": "success",
                "job_id": job_id
            }

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from scheduler service: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error forwarding to scheduler service: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error forwarding to scheduler service: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )
        
        except Exception as e:
            logger.error(f"Unexpected error in scheduler service: {e}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error in scheduler service: {e}"
            )
