"""
This module defines the FastAPI router for managing scheduled jobs in the scheduler service.

Routes:
    - GET    /           : Retrieve a list of all scheduled jobs.
    - POST   /           : Add a new job to the scheduler.
    - DELETE /{job_id}   : Remove a scheduled job by its job ID.
    - POST   /{job_id}/pause  : Pause a scheduled job by its job ID.
    - POST   /{job_id}/resume : Resume a scheduled job by its job ID.

Each route delegates the core logic to corresponding service functions and returns
responses in standardized formats. The module uses Pydantic models for request and
response validation and logging for traceability.
"""
from app.services.remove_job import _remove_job
from app.services.list_jobs import _list_jobs
from app.services.pause_job import _pause_job
from app.services.resume_job import _resume_job
from app.services.add_job import _add_job

from typing import Dict, List

from shared.models.scheduler import JobResponse, SchedulerJobRequest

from shared.log_config import get_logger
logger = get_logger(f"scheduler.{__name__}")

from fastapi import APIRouter
router = APIRouter()


@router.get("", response_model=List[JobResponse])
def list_jobs() -> List[JobResponse]:
    """
    Retrieve a list of scheduled jobs.

    Returns:
        List[JobResponse]: A list of job response objects representing the scheduled jobs.
    """
    return _list_jobs()


@router.post("", response_model=JobResponse)
def add_job(job_request: SchedulerJobRequest) -> JobResponse:
    """
    Add a new scheduled job to the scheduler.

    Args:
        job_request (SchedulerJobRequest): Details of the job to be scheduled, including 
        trigger type ('date', 'interval', or 'cron'), execution parameters, and metadata.

    Returns:
        JobResponse: Details of the successfully added job, including job ID, 
        next run time, trigger type, and metadata.

    Raises:
        HTTPException: 
        - 400 Bad Request if trigger parameters are invalid or missing
        - 409 Conflict if a job with the same ID already exists
        - 500 Internal Server Error for unexpected scheduling errors
    """
    return _add_job(job_request)


@router.delete("/{job_id}", response_model=Dict[str, str])
def remove_job(job_id: str) -> Dict[str, str]:
    """
    Removes a scheduled job by its job ID.

    Args:
        job_id (str): The unique identifier of the job to be removed.

    Returns:
        Dict[str, str]: A dictionary containing the result of the removal operation.
    """
    return _remove_job(job_id)


@router.post("/{job_id}/pause", response_model=Dict[str, str])
def pause_job(job_id: str) -> Dict[str, str]:
    """
    Pause a scheduled job by its job ID.

    Args:
        job_id (str): The unique identifier of the job to be paused.

    Returns:
        Dict[str, str]: A dictionary containing the result of the pause operation.
    """
    return _pause_job(job_id)


@router.post("/{job_id}/resume", response_model=Dict[str, str])
def resume_job(job_id: str) -> Dict[str, str]:
    """
    Resume a scheduled job by its job ID.

    Args:
        job_id (str): The unique identifier of the job to be resumed.

    Returns:
        Dict[str, str]: A dictionary containing the result of the resume operation.
    """
    return _resume_job(job_id)