"""
This module defines a job scheduler function `summarize_user_buffers` that triggers a summary process
for inactive user buffers by interacting with the ledger service. It also provides an example of how
to create a job for this function using an HTTP POST request to the scheduler service.
Functions:
  summarize_user_buffers():
    Sends a POST request to the ledger service to process and summarize inactive user buffers.
    Logs the result or any errors encountered during the process.
Example:
  The example demonstrates how to create a job for the `summarize_user_buffers` function using
  the scheduler service. It includes the job request payload and the HTTP POST request to register
  the job with the scheduler.
Dependencies:
  - shared.config.TIMEOUT: Timeout value for HTTP requests.
  - shared.consul.get_service_address: Retrieves the service address for a given service name.
  - shared.log_config.get_logger: Configures and retrieves a logger instance.
  - httpx: Library for making HTTP requests.
"""
from shared.config import TIMEOUT

import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx


def summarize_user_buffers():
    """
    Trigger a summary process for inactive user buffers by sending a POST request to the ledger service.
    
    This function attempts to call the ledger service's inactive summaries endpoint to process and summarize
    user buffers that are currently inactive. It logs the result on successful execution and logs any
    errors that occur during the process.
    
    Raises:
        Exception: If the HTTP request to the ledger service fails or times out.
    """
    ledger_address, ledger_port = shared.consul.get_service_address('ledger')
    url = f"http://{ledger_address}:{ledger_port}/summaries/inactive"
    try:
        response = httpx.post(url, timeout=TIMEOUT)
        response.raise_for_status()
        logger.debug(f"Scheduler triggered summarize_user_buffers(): {response.json()}")

    except Exception as e:
        logger.error(f"Failed to trigger summarize_user_buffers(): {e}")


"""
create this job with:

import httpx

job_request = {
  "external_url": "http://brain:4207/scheduler/callback",
  "trigger": "interval",
  "interval_minutes": 1,
  "metadata": {
    "function": "summarize_user_buffers"
  }
}

brain_address, brain_port = shared.consul.get_service_address('brain')
url = f"http://{brain_address}:{brain_port}/scheduler/job"

response = httpx.post(url, json=job_request, timeout=60)
print(response.json())
"""