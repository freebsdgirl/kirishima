"""
This module provides functionality to pause a running job in the scheduler.

Functions:
    _pause_job(job_id: str) -> Dict[str, str]:
        Pauses the specified job in the scheduler and returns a status response.
        Raises an HTTPException with a 500 status code if an error occurs.
"""
from typing import Dict

from shared.log_config import get_logger
logger = get_logger(f"scheduler.{__name__}")

from app.util import scheduler

from fastapi import HTTPException, status


def _pause_job(job_id: str) -> Dict[str, str]:
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