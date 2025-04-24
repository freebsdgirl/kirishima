import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx


def summarize_user_buffers():
    ledger_address, ledger_port = shared.consul.get_service_address('ledger')
    url = f"http://{ledger_address}:{ledger_port}/summaries/inactive"
    try:
        response = httpx.post(url, timeout=60)
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