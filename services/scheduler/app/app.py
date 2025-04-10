"""
This module implements a FastAPI application for managing scheduled jobs using APScheduler.
The application provides endpoints for:
- Health check (`/ping`)
- Listing all API routes (`/__list_routes__`)
- Adding a new job (`/jobs`)
- Removing a job (`/jobs/{job_id}`)
- Listing all scheduled jobs (`/jobs`)
- Pausing a job (`/jobs/{job_id}/pause`)
- Resuming a job (`/jobs/{job_id}/resume`)
The scheduler is configured with:
- SQLAlchemyJobStore for persistent job storage using SQLite.
- ThreadPoolExecutor for concurrent job execution.
- Job defaults to prevent coalescing and limit concurrent job instances.
Key Components:
- `execute_job`: Function to execute a scheduled job by sending a POST request to an external URL.
- `JobResponse`: Pydantic model representing the response structure for job details.
- `SchedulerJobRequest`: Pydantic model (imported) representing the request structure for scheduling a job.
Endpoints:
1. `/ping` (GET): Health check endpoint to verify service status.
2. `/__list_routes__` (GET): Lists all registered API routes.
3. `/jobs` (POST): Adds a new scheduled job with a one-time or recurring trigger.
4. `/jobs/{job_id}` (DELETE): Removes a scheduled job by its ID.
5. `/jobs` (GET): Retrieves a list of all scheduled jobs.
6. `/jobs/{job_id}/pause` (POST): Pauses a running job by its ID.
7. `/jobs/{job_id}/resume` (POST): Resumes a previously paused job by its ID.
Error Handling:
- Returns appropriate HTTP status codes and error messages for invalid requests or internal errors.
- Logs errors and exceptions for debugging purposes.
Dependencies:
- APScheduler for job scheduling.
- FastAPI for building the web application.
- Pydantic for request/response validation.
- Requests for making HTTP requests during job execution.
- Shared modules for configuration, logging, and models.
"""

import app.config as config

from app.docs import router as docs_router

from shared.log_config import get_logger
logger = get_logger(__name__)

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

from fastapi import FastAPI, HTTPException, status
from fastapi.routing import APIRoute
app = FastAPI()
app.include_router(docs_router, tags=["docs"])


"""
Health check endpoint that returns the service status.

Returns:
    Dict[str, str]: A dictionary with a 'status' key indicating the service is operational.
"""
@app.get("/ping")
def ping():
    return {"status": "ok"}


"""
Endpoint to list all registered API routes in the application.

Returns:
    List[Dict[str, Union[str, List[str]]]]: A list of dictionaries containing route paths and their supported HTTP methods.
"""
@app.get("/__list_routes__")
def list_routes():
    return [
        {"path": route.path, "methods": list(route.methods)}
        for route in app.routes
        if isinstance(route, APIRoute)
    ]


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
