"""
This module provides functionality to add new scheduled jobs to the application's scheduler.
Functions:
    _add_job(job_request: SchedulerJobRequest) -> JobResponse
        Adds a new job to the scheduler based on the provided job request details.
        Supports 'date', 'interval', and 'cron' triggers, and validates required parameters
        for each trigger type. Handles job ID conflicts and unexpected scheduling errors,
        returning appropriate HTTP exceptions when necessary.
        - 400 Bad Request for invalid or missing trigger parameters.
        - 409 Conflict if a job with the same ID already exists.
        - 500 Internal Server Error for unexpected scheduling errors.
"""
from app.util import scheduler, execute_job

from shared.models.scheduler import SchedulerJobRequest, JobResponse

import uuid

from shared.log_config import get_logger
logger = get_logger(f"scheduler.{__name__}")

from fastapi import HTTPException, status


def _add_job(job_request: SchedulerJobRequest) -> JobResponse:
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