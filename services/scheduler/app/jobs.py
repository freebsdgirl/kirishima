"""
This module provides FastAPI endpoints for managing scheduled jobs using APScheduler.
Endpoints:
    - POST /jobs: Add a new scheduled job (one-time or recurring).
    - DELETE /jobs/{job_id}: Remove a scheduled job by its ID.
    - GET /jobs: List all scheduled jobs.
Functions:
    - add_job(job_request: SchedulerJobRequest) -> JobResponse:
        Creates a new scheduled job with the specified trigger and parameters.
        Supports 'date' (one-time) and 'interval' (recurring) triggers.
        Returns job details or raises HTTPException on error.
    - remove_job(job_id: str) -> Dict[str, str]:
        Removes a scheduled job by its unique identifier.
        Returns a status message or raises HTTPException if the job is not found or on error.
    - list_jobs() -> List[JobResponse]:
        Retrieves a list of all scheduled jobs, including their IDs, next run times, trigger types, and metadata.
Dependencies:
    - FastAPI for API routing and HTTP exception handling.
    - APScheduler for job scheduling.
    - Shared models for request and response schemas.
    - Logging for debug and error reporting.
"""

from app.util import scheduler, execute_job

from shared.models.scheduler import SchedulerJobRequest, JobResponse

from typing import Dict, List
import uuid

from apscheduler.jobstores.base import JobLookupError

from shared.log_config import get_logger
logger = get_logger(f"scheduler.{__name__}")

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/jobs", response_model=JobResponse)
def add_job(job_request: SchedulerJobRequest) -> JobResponse:
    """
    Create a new scheduled job with either a one-time or recurring trigger.

    Args:
        job_request (JobRequest): Details for the job to be scheduled, including:
            - external_url: The endpoint to call when the job runs
            - trigger: Type of job scheduling ('date' or 'interval')
            - run_date: Specific datetime for one-time jobs
            - interval_minutes: Frequency for recurring jobs
            - metadata: Optional additional job information

    Returns:
        JobResponse: Details of the created job, including job ID, next run time, 
        trigger type, and metadata.

    Raises:
        HTTPException: If invalid job parameters are provided or scheduling fails.
    """
    logger.debug(f"Adding job with request: {job_request.json()}")
    try:
        job_id = job_request.id or str(uuid.uuid4())

        if scheduler.get_job(job_id):
            logger.error(f"Job {job_id} already exists.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job {job_id} already exists."
            )

        job_kwargs = {
            "external_url": job_request.external_url,
            "metadata": job_request.metadata
        }

        if job_request.trigger == "date":
            if not job_request.run_date:
                logger.error("run_date must be provided for 'date' trigger")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="run_date must be provided for 'date' trigger"
                )

            job = scheduler.add_job(
                func=execute_job,
                trigger='date',
                run_date=job_request.run_date,
                kwargs=job_kwargs,
                id=job_id
            )

        elif job_request.trigger == "interval":
            if not job_request.interval_minutes:
                logger.error("interval_minutes must be provided for 'interval' trigger")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="interval_minutes must be provided for 'interval' trigger"
                )

            job = scheduler.add_job(
                func=execute_job,
                trigger='interval',
                minutes=job_request.interval_minutes,
                kwargs=job_kwargs,
                id=job_id
            )

        else:
            logger.error("Unsupported trigger type")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported trigger type. Use 'date' or 'interval'."
            )
        
        response = JobResponse(
            job_id=job.id,
            next_run_time=job.next_run_time,
            trigger=job_request.trigger,
            metadata=job_request.metadata
        )

        logger.info(f"Job {job_id} added successfully: {response.model_dump_json()}")
        return response

    except HTTPException as he:
        raise he

    except Exception as e:
        logger.error(f"Error adding job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error adding job: {str(e)}"
        )


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


@router.get("/jobs", response_model=List[JobResponse])
def list_jobs() -> List[JobResponse]:
    """
    Retrieve a list of all scheduled jobs in the scheduler.

    Returns:
        List[JobResponse]: A list of job details including job ID, next run time, 
        trigger type, and associated metadata. Trigger types are identified as 
        'date', 'interval', or 'unknown'.
    """
    logger.debug("/jobs Request")
    jobs = scheduler.get_jobs()
    response = []

    for job in jobs:
        trigger_type = "unknown"

        # Identify the trigger type by the trigger's class name.
        if job.trigger.__class__.__name__ == "DateTrigger":
            trigger_type = "date"
        elif job.trigger.__class__.__name__ == "IntervalTrigger":
            trigger_type = "interval"

        response.append(JobResponse(
            job_id=job.id,
            next_run_time=job.next_run_time,
            trigger=trigger_type,
            metadata=job.kwargs.get("metadata", {})
        ))

    return response
