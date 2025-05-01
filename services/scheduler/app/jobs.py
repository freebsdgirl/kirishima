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
    logger.debug(f"Adding job with request: {job_request.model_dump_json(indent=4)}")

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

        elif job_request.trigger == "cron":
            if job_request.hour is None or job_request.minute is None:
                logger.error("hour and minute must be provided for 'cron' trigger")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="hour and minute must be provided for 'cron' trigger"
                )

            cron_kwargs = {
                "hour": job_request.hour,
                "minute": job_request.minute,
            }
            if job_request.day_of_week is not None:
                cron_kwargs["day_of_week"] = job_request.day_of_week
            if job_request.day is not None:
                cron_kwargs["day"] = job_request.day

            job = scheduler.add_job(
                func=execute_job,
                trigger='cron',
                kwargs=job_kwargs,
                id=job_id,
                **cron_kwargs
            )

        else:
            logger.error("Unsupported trigger type")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported trigger type. Use 'date', 'interval', or 'cron'."
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
        'date', 'interval', or 'cron'.
    """
    logger.debug("/jobs Request")
    jobs = scheduler.get_jobs()
    response = []

    for job in jobs:
        trigger_type = "unknown"

        # Identify the trigger type by the trigger's class name.
        trigger_class = job.trigger.__class__.__name__
        if trigger_class == "DateTrigger":
            trigger_type = "date"
        elif trigger_class == "IntervalTrigger":
            trigger_type = "interval"
        elif trigger_class == "CronTrigger":
            trigger_type = "cron"

        response.append(JobResponse(
            job_id=job.id,
            next_run_time=job.next_run_time,
            trigger=trigger_type,
            metadata=job.kwargs.get("metadata", {})
        ))

    return response
