import app.config

from shared.log_config import get_logger

logger = get_logger(__name__)

from pydantic import BaseModel
from typing import Dict, Any, Optional
import requests
from fastapi import HTTPException, status

class SchedulerJobRequest(BaseModel):
    """
    Represents a request to schedule a job with configurable execution parameters.
    
    Attributes:
        external_url (str): The URL of the external service or endpoint to be triggered.
        trigger (str): The type of job scheduling trigger, either 'date' or 'interval'.
        run_date (Optional[str]): An ISO datetime string specifying the exact time to run the job.
        interval_minutes (Optional[int]): Number of minutes between job executions for interval-based triggers.
        metadata (Optional[Dict[str, Any]]): Additional key-value metadata associated with the job.
    """
    external_url: str
    trigger: str  # 'date' or 'interval'
    run_date: Optional[str] = None  # ISO datetime string
    interval_minutes: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = {}


def add_job(job_name, job_time):
    """
    Add a job to the scheduler.
    
    Args:
        job_name (str): The name of the job to be added.
        job_time (str): The interval at which the job should run in HH:MM:SS format.
    
    Returns:
        dict: A success status message indicating the job was added.
    
    Raises:
        HTTPException: If there is an error during job addition, with a 500 Internal Server Error.
    """
    logger.debug(f"Adding job {job_name} with time {job_time}.")
    try:
        # Step 1: Parse time string into seconds
        hours, minutes, seconds = map(int, job_time.split(":"))
        total_seconds = hours * 3600 + minutes * 60 + seconds

        job_id = f"{job_name}_every_{job_time}m"

        # Step 2: Construct SchedulerJobRequest-compatible payload
        payload = {
            "id": job_id,
            "external_url": f"{app.config.BRAIN_API_URL}/scheduler/callback",  # centralized callback
            "trigger": "interval",
            "interval_minutes": max(1, total_seconds // 60),  # APScheduler only takes minutes
            "metadata": {
                "function": job_name
            }
        }

        # Step 3: Send to Brain
        response = requests.post(f"{app.config.BRAIN_API_URL}/scheduler/job", json=payload)
        response.raise_for_status()
        return response.json()

    except requests.HTTPError as e:
        if e.response.status_code == 409:
            logger.info(f"Job {job_id} already exists. Skipping.")
            return  # Treat it as success, don't raise
        else:
            logger.error(f"Scheduler error: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=e.response.text
            )

    except requests.RequestException as e:
        logger.error(f"Failed to schedule job {job_name}: {str(e)}")
        return


def delete_job(job_id: str):
    """
    Delete a scheduled job from the Brain scheduler.
    
    Args:
        job_id (str): The unique identifier of the job to be deleted.
    
    Returns:
        dict: A response from the scheduler indicating the job deletion status.
    
    Raises:
        HTTPException: If there is an error deleting the job, with either the original error 
        status code or a 503 Service Unavailable status.
    """
    logger.debug(f"Deleting job: {job_id}")
    try:
        response = requests.delete(f"{app.config.BRAIN_API_URL}/scheduler/job/{job_id}")
        response.raise_for_status()
        logger.info(f"Job {job_id} deleted successfully.")
        return f"🗑️ Deleted job `{job_id}` successfully."

    except requests.exceptions.HTTPError as e:
        logger.error(f"Brain error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.text or str(e)
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"Brain unreachable: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Brain unreachable: {str(e)}"
        )


def list_jobs():
    """
    Retrieve and format a list of currently scheduled jobs from the Brain scheduler.
    
    Returns:
        str: A formatted string listing job details, or "No scheduled jobs found" if no jobs exist.
    
    Raises:
        HTTPException: If there is an error retrieving jobs from the scheduler, 
        with either the original error status code or a 503 Service Unavailable status.
    """
    logger.debug(f"Listing jobs")
    try:
        response = requests.get(f"{app.config.BRAIN_API_URL}/scheduler/job")
        response.raise_for_status()
        logger.info(f"Jobs listed successfully: {response.json()}")
        
        results = response.json()
        if not results:
            return "No scheduled jobs found."

        lines = []
        for job in results:
            job_id = job.get("job_id", "unknown")
            trigger = job.get("trigger", "unknown")
            metadata = job.get("metadata", {})
            func = metadata.get("function", "unknown")
            next_run = job.get("next_run_time", "unscheduled")

            line = f"🛠️ {job_id} → {func} (trigger: {trigger}, next run: {next_run})"
            lines.append(line)

        return "\n".join(lines)

    except requests.exceptions.HTTPError as e:
        logger.error(f"Scheduler error: {response.status_code} - {response.text}")
        status_code=e.response.status_code
        detail=e.response.text or str(e)

        raise HTTPException(status_code, detail)
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Brain unreachable: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Brain unreachable: {str(e)}"
        )
