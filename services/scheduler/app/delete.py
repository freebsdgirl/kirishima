"""
This module provides an API endpoint for removing scheduled jobs from the application's scheduler.

Endpoints:
    DELETE /jobs/{job_id}:
        Removes a scheduled job identified by the given job_id.

Dependencies:
    - FastAPI for API routing and exception handling.
    - APScheduler for job scheduling and management.
    - Shared logging configuration for consistent logging.

Functions:
    remove_job(job_id: str) -> Dict[str, str]:
        Removes a job from the scheduler by its unique identifier.
        Returns a success message if the job is removed.
        Raises HTTP 404 if the job is not found.
        Raises HTTP 500 for other errors.
"""
from app.util import scheduler

from typing import Dict

from apscheduler.jobstores.base import JobLookupError

from shared.log_config import get_logger
logger = get_logger(f"scheduler.{__name__}")

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.delete("/jobs/{job_id}", response_model=Dict[str, str])
def remove_job(job_id: str) -> Dict[str, str]:
    """
    Remove a scheduled job from the scheduler.

    Args:
        job_id (str): The unique identifier of the job to be removed.

    Returns:
        dict: A status response indicating successful job removal.

    Raises:
        HTTPException: If there is an error removing the job, with a 500 Internal Server Error.
    """
    logger.debug(f"DELETE /jobs/{job_id}")
    try:
        scheduler.remove_job(job_id)
        return {
            "status": "success", 
            "message": f"Job {job_id} removed."
        }
    except JobLookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found."
        )
    except Exception as e:
        logger.error(f"Error removing job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
