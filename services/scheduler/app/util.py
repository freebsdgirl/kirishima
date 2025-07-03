"""
This module configures and manages a background job scheduler using APScheduler with a persistent
SQLAlchemy job store and a thread pool executor. It loads scheduler configuration from a JSON file,
sets up job storage in a SQLite database, and defines job execution defaults to prevent coalescing
and limit concurrent job instances.

The module provides:
- Initialization of the BackgroundScheduler with custom job stores, executors, and job defaults.
- A utility function `execute_job` to send job execution metadata to an external URL via HTTP POST,
    logging the outcome of each execution attempt.

Dependencies:
- APScheduler for scheduling and job management.
- SQLAlchemy for persistent job storage.
- Requests for HTTP communication.
- A shared logging configuration for consistent logging.
"""
from shared.log_config import get_logger
logger = get_logger(f"scheduler.{__name__}")

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from typing import Dict, Any
from datetime import datetime
import requests
import json

"""
Configures the background scheduler with SQLAlchemy job store, thread pool executor, and job defaults.

Sets up a scheduler that uses a SQLite database for persistent job storage, a thread pool
for concurrent job execution, and default settings to control job behavior such as 
preventing job coalescing and limiting concurrent job instances.
"""


with open('/app/config/config.json') as f:
    _config = json.load(f)

db = _config["db"]["scheduler"]

jobstores = {
    'default': SQLAlchemyJobStore(url=f"sqlite:///{db}")
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
