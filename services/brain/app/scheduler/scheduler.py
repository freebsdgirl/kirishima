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
    - shared.log_config: Logging configuration
    - httpx: Asynchronous HTTP client
    - fastapi: API routing and exception handling
    - shared.config: Configuration for TIMEOUT
    - app.scheduler.job_summarize: Function to summarize user buffers
"""
from shared.models.scheduler import SchedulerCallbackRequest

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import inspect
import json


from fastapi import APIRouter, HTTPException, status
router = APIRouter()

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]



from app.scheduler.job_notification import check_notifications

globals()["check_notifications"]                = check_notifications

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
