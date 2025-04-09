"""
This module provides a FastAPI application for managing scheduled jobs using APScheduler.
The application includes endpoints for creating, listing, pausing, resuming, and deleting jobs.
Jobs can be scheduled with either a one-time trigger or a recurring interval trigger. The scheduler
uses a SQLite database for persistent job storage and supports concurrent job execution.
Modules and Classes:
- `JobResponse`: A Pydantic model representing the details of a scheduled job.
- `SchedulerJobRequest`: A shared model for job request details, imported from `shared.models.scheduler`.
Endpoints:
1. `/ping` (GET): Health check endpoint to verify the service is running.
2. `/jobs` (POST): Create a new scheduled job.
3. `/jobs` (GET): Retrieve a list of all scheduled jobs.
4. `/jobs/{job_id}` (DELETE): Remove a scheduled job by its ID.
5. `/jobs/{job_id}/pause` (POST): Pause a running job.
6. `/jobs/{job_id}/resume` (POST): Resume a previously paused job.
Scheduler Configuration:
- Uses `SQLAlchemyJobStore` for persistent job storage.
- Configured with a `ThreadPoolExecutor` for concurrent job execution.
- Default job settings include no coalescing and a maximum of one concurrent instance per job.
Functions:
- `execute_job(external_url: str, metadata: Dict[str, Any])`: Executes a scheduled job by sending a POST request to an external URL.
- `add_job(job_request: SchedulerJobRequest) -> JobResponse`: Creates a new scheduled job with the specified trigger and metadata.
- `remove_job(job_id: str) -> Dict[str, str]`: Removes a scheduled job from the scheduler.
- `list_jobs() -> List[JobResponse]`: Lists all scheduled jobs with their details.
- `pause_job(job_id: str) -> Dict[str, str]`: Pauses a running job.
- `resume_job(job_id: str) -> Dict[str, str]`: Resumes a previously paused job.
Logging:
- Logs are generated for all operations, including job creation, execution, and errors.
- Uses a shared logging configuration from `shared.log_config`.
Error Handling:
- Returns appropriate HTTP status codes and error messages for invalid requests or internal errors.
- Handles job conflicts, missing parameters, and unsupported trigger types with detailed error responses.
"""
import app.config as config
from app.docs import router as docs_router

from shared.models.scheduler import SchedulerJobRequest

import uuid
from typing import Optional, Dict, Any, List
import requests
from datetime import datetime
from pydantic import BaseModel

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.base import JobLookupError

from shared.log_config import get_logger
logger = get_logger(__name__)

from fastapi import FastAPI, HTTPException, status
app = FastAPI()
app.include_router(docs_router)


db_path = config.SCHEDULER_DB

@app.get("/ping")
def ping():
    return {"status": "ok"}


class JobResponse(BaseModel):
    """
    Response model representing the details of a scheduled job.
    
    Attributes:
        job_id (str): Unique identifier for the scheduled job.
        next_run_time (Optional[datetime]): Timestamp of the next scheduled job execution.
        trigger (str): Type of job trigger ('date' or 'interval').
        metadata (Dict[str, Any]): Additional metadata associated with the job.
    """
    job_id: str
    next_run_time: Optional[datetime]
    trigger: str
    metadata: Dict[str, Any]


"""
Configures the background scheduler with SQLAlchemy job store, thread pool executor, and job defaults.

Sets up a scheduler that uses a SQLite database for persistent job storage, a thread pool
for concurrent job execution, and default settings to control job behavior such as 
preventing job coalescing and limiting concurrent job instances.
"""
jobstores = {
    'default': SQLAlchemyJobStore(url=f"sqlite:///{config.SCHEDULER_DB}")
}

executors = {
    'default': ThreadPoolExecutor(10)
}

job_defaults = {
    'coalesce': False,
    'max_instances': 1
}

scheduler = BackgroundScheduler(
    jobstores=jobstores,
    executors=executors,
    job_defaults=job_defaults
)

scheduler.start()


def execute_job(external_url: str, metadata: Dict[str, Any]):
    """
    Execute a scheduled job by sending a POST request to the specified external URL.

    Constructs a payload with job metadata and current timestamp, then sends a POST request
    to the external endpoint. Logs successful job execution or any errors encountered.

    Args:
        external_url (str): The URL endpoint to which the job payload will be sent.
        metadata (Dict[str, Any]): Additional context or information associated with the job.
    """
    logger.debug(f"Executing job with metadata: {metadata}")
    payload = {
        "metadata": metadata,
        "executed_at": datetime.now().isoformat()
    }

    try:
        response = requests.post(external_url, json=payload)
        response.raise_for_status()
        logger.info(f"Job executed successfully, response: {response.text}")

    except Exception as e:
        logger.error(f"Error executing job: {e}")


@app.post("/jobs", response_model=JobResponse)
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
        # Generate a unique job ID.
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
            raise HTTPException(
                logger.error("Unsupported trigger type"),
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported trigger type. Use 'date' or 'interval'."
            )
        
        response = JobResponse(
            job_id=job.id,
            next_run_time=job.next_run_time,
            trigger=job_request.trigger,
            metadata=job_request.metadata
        )

        logger.info(f"Job {job_id} added successfully: {response.json()}")
        return response

    except HTTPException as he:
        raise he

    except Exception as e:
        logger.error(f"Error adding job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=str(e)
        )


@app.delete("/jobs/{job_id}", response_model=Dict[str, str])
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
    logger.debug(f"Removing job {job_id}")
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


@app.get("/jobs", response_model=List[JobResponse])
def list_jobs() -> List[JobResponse]:
    """
    Retrieve a list of all scheduled jobs in the scheduler.

    Returns:
        List[JobResponse]: A list of job details including job ID, next run time, 
        trigger type, and associated metadata. Trigger types are identified as 
        'date', 'interval', or 'unknown'.
    """
    logger.debug("Listing jobs")
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


@app.post("/jobs/{job_id}/pause", response_model=Dict[str, str])
def pause_job(job_id: str) -> Dict[str, str]:
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
            detail=str(e)
        )


@app.post("/jobs/{job_id}/resume", response_model=Dict[str, str])
def resume_job(job_id: str) -> Dict[str, str]:
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
            detail=str(e)
        )
