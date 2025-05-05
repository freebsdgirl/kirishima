"""
This module provides functionality to asynchronously check and execute notifications.
Functions:
    check_notifications():
        Asynchronously executes notifications by calling the notification_execute() method.
        Logs and raises an HTTPException with a 500 status code if an unexpected error occurs.
"""
from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from app.notification.callback import notification_execute

from fastapi import HTTPException, status


async def check_notifications():
    """
    Asynchronously check and execute notifications.
    
    This function attempts to execute notifications via the notification_execute() method.
    If an error occurs during notification execution, it logs the error and raises an HTTPException
    with a 500 Internal Server Error status code.
    
    Raises:
        HTTPException: If an unexpected error occurs during notification execution.
    """
    try:
        await notification_execute()

    except Exception as e:
        logger.error(f"Error executing notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while executing notification: {e}"
        )

    except Exception as e:
        logger.error(f"Error executing notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while executing notification: {e}"
        )

"""
create this job with:

import httpx

request = {
    "external_url": "http://brain:4207/scheduler/callback",
    "trigger": "interval",
    "interval_minutes": 1,
    "metadata": {
        "function": "check_notifications"
    }
}

response = await httpx.post("http://127.0.0.1:4207/scheduler/job", json=request)
"""