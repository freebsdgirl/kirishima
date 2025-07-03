"""
This module provides FastAPI endpoints to pause and resume scheduled jobs.

Endpoints:
    - POST /jobs/{job_id}/pause: Pauses a running job identified by job_id.
    - POST /jobs/{job_id}/resume: Resumes a previously paused job identified by job_id.

Each endpoint returns a JSON response indicating the status and message of the operation.
If an error occurs during the pause or resume operation, an HTTP 500 error is returned.

Dependencies:
    - shared.log_config.get_logger: For logging actions and errors.
    - app.util.scheduler: Contains the logic to pause and resume jobs.
    - fastapi: For API routing and exception handling.
"""
from typing import Dict

from shared.log_config import get_logger
logger = get_logger(f"scheduler.{__name__}")

from app.util import scheduler

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/jobs/{job_id}/pause", response_model=Dict[str, str])
def pause_job(job_id: str) -> Dict[str, str]:
    """
    Pause a running job in the scheduler.

    Args:
        job_id (str): The unique identifier of the job to be paused.

    Returns:
        dict: A status response indicating successful job pause.

    Raises:
        HTTPException: If there is an error pausing the job, with a 500 Internal Server Error.
    """
    logger.debug(f"Pausing job {job_id}")
    try:
        scheduler.pause_job(job_id)
        return {
            "status": "success", 
            "message": f"Job {job_id} paused."
    }

    except Exception as e:
        logger.error(f"Error pausing job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error pausing job {job_id}: {e}"
        )


@router.post("/jobs/{job_id}/resume", response_model=Dict[str, str])
def resume_job(job_id: str) -> Dict[str, str]:
    """
    Resume a previously paused job in the scheduler.

    Args:
        job_id (str): The unique identifier of the job to be resumed.

    Returns:
        dict: A status response indicating successful job resumption.

    Raises:
        HTTPException: If there is an error resuming the job, with a 500 Internal Server Error.
    """
    logger.debug(f"Resuming job {job_id}")
    try:
        scheduler.resume_job(job_id)
        return {
            "status": "success", 
            "message": f"Job {job_id} resumed."
        }

    except Exception as e:
        logger.error(f"Error resuming job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resuming job {job_id}: {e}"
        )