"""
This module configures and manages a background job scheduler for the application.

It sets up a persistent job store using SQLite, a thread pool executor for concurrent job execution,
and default job settings to control execution behavior. The module provides a utility function to
execute scheduled jobs by sending HTTP POST requests to external endpoints, including job metadata
and execution timestamps in the payload. Logging is integrated for monitoring job execution and errors.
"""
import app.config

from shared.log_config import get_logger
logger = get_logger(f"scheduler.{__name__}")

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from typing import Dict, Any
from datetime import datetime
import requests


"""
Configures the background scheduler with SQLAlchemy job store, thread pool executor, and job defaults.

Sets up a scheduler that uses a SQLite database for persistent job storage, a thread pool
for concurrent job execution, and default settings to control job behavior such as 
preventing job coalescing and limiting concurrent job instances.
"""
jobstores = {
    'default': SQLAlchemyJobStore(url=f"sqlite:///{app.config.SCHEDULER_DB}")
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
