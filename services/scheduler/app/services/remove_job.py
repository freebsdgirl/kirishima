"""
This module provides functionality to remove a scheduled job from the scheduler.

Functions:
    _remove_job(job_id: str) -> Dict[str, str]:
        Removes a job from the scheduler by its unique identifier.
        Logs the removal attempt and handles errors by raising appropriate HTTP exceptions.
"""
from app.util import scheduler

from typing import Dict

from apscheduler.jobstores.base import JobLookupError

from shared.log_config import get_logger
logger = get_logger(f"scheduler.{__name__}")

from fastapi import HTTPException, status


def _remove_job(job_id: str) -> Dict[str, str]:
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
