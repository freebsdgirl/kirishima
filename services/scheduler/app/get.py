"""
This module defines the FastAPI route for retrieving a list of all scheduled jobs
from the scheduler service.

Routes:
    - GET /jobs: Returns a list of all scheduled jobs, including job ID, next run time,
      trigger type ('date', 'interval', or 'cron'), and associated metadata.

Dependencies:
    - app.util.scheduler: Provides access to the scheduler instance.
    - shared.models.scheduler.JobResponse: Response model for job details.
    - shared.log_config.get_logger: Logger configuration for request logging.
    - fastapi.APIRouter, HTTPException, status: FastAPI routing and exception handling.

Logging:
    - Logs incoming requests and errors encountered during job processing.
"""
from app.util import scheduler

from shared.models.scheduler import JobResponse

from typing import List

from shared.log_config import get_logger
logger = get_logger(f"scheduler.{__name__}")

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


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
