"""
This module provides functionality to resume a previously paused job in the scheduler.

Functions:
    _resume_job(job_id: str) -> Dict[str, str]:
        Resumes a paused job identified by the given job_id. Returns a status response on success,
        or raises an HTTPException with a 500 status code if an error occurs.
"""
from typing import Dict

from shared.log_config import get_logger
logger = get_logger(f"scheduler.{__name__}")

from app.util import scheduler

from fastapi import HTTPException, status


def _resume_job(job_id: str) -> Dict[str, str]:
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