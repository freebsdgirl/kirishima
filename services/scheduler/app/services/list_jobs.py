"""
Module for listing all scheduled jobs in the scheduler service.

This module provides a function to retrieve and format details about all jobs currently
scheduled in the system. It handles identification of trigger types, extraction of job
metadata, and error handling for jobs with incomplete or missing metadata.

Functions:
    _list_jobs() -> List[JobResponse]:
        Retrieves a list of all scheduled jobs, including job ID, next run time,
        trigger type ('date', 'interval', or 'cron'), and associated metadata.
        Raises an HTTPException if a job cannot be processed due to missing or invalid data.
"""
from app.util import scheduler

from shared.models.scheduler import JobResponse

from typing import List

from shared.log_config import get_logger
logger = get_logger(f"scheduler.{__name__}")

from fastapi import HTTPException, status


def _list_jobs() -> List[JobResponse]:
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

        # there's a weird edge case where sometimes metadata is not set, which causes an error.
        # this happens when a job is only partially created but creation fails due to metadata = None.
        try:
            response.append(JobResponse(
                job_id=job.id,
                external_url=job.kwargs.get("external_url", ""),
                next_run_time=job.next_run_time,
                trigger=trigger_type,
                metadata=job.kwargs.get("metadata", {})
            ))
        except Exception as e:
            logger.error(f"Error processing job {job.id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing job {job.id}"
            )

    return response