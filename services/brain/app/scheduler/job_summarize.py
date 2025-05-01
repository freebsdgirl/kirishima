"""
This module defines asynchronous job functions for generating user summary reports
for different periods of the day (night, morning, afternoon, evening) and for the daily summary.
Functions:
    - summarize_user_buffer_night: Creates a night summary for the current date.
    - summarize_user_buffer_morning: Creates a morning summary for the current date.
    - summarize_user_buffer_afternoon: Creates an afternoon summary for the current date.
    - summarize_user_buffer_evening: Creates an evening summary and a daily summary for the previous day.
Each function:
    - Constructs a SummaryCreateRequest payload for the appropriate period and date.
    - Calls the relevant summary creation function (create_summary or create_daily_summary).
    - Logs the summary creation process.
    - Handles exceptions by logging errors and raising HTTP 500 Internal Server Error responses.
The module is intended to be used with a scheduler that triggers these jobs at specific times of day,
as described in the example job request payloads at the end of the file.
"""
from shared.config import TIMEOUT

from app.summary.create_user_periodic_summary import create_summary
from app.summary.daily import create_daily_summary
from app.summary.weekly import create_weekly_summary
from app.summary.monthly import create_monthly_summary

from shared.models.summary import SummaryCreateRequest, Summary

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from typing import List
from datetime import datetime, timedelta
import shared.consul
import httpx

from fastapi import HTTPException, status


async def delete_user_buffer_from_summaries(request: List[Summary]):
    """
    Delete user buffers from summaries across multiple users.
    
    This function takes a list of summaries, extracts unique user IDs, and then
    deletes the corresponding user buffers via the ledger service's delete endpoint.
    
    Args:
        request (List[Summary]): A list of summary objects containing user metadata.
    
    Raises:
        HTTPException: If there are errors during the buffer deletion process,
        with specific error details and appropriate HTTP status codes.
    """
    user_ids = set()
    for summary in request:
        user_ids.add(summary.metadata.user_id)

    # step through each user id and delete the buffer for that user id
    for user_id in user_ids:
        logger.debug(f"Deleting buffer for user {user_id}")
        # call ledger's delete /user/{user_id} endpoint
        
        ledger_address, ledger_port = shared.consul.get_service_address('ledger')

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.delete(f"http://{ledger_address}:{ledger_port}/user/{user_id}")
                response.raise_for_status()
                logger.debug(f"Buffer deleted for user {user_id}")

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Error deleting buffer for user {user_id}: {e.response.text}"
            )

        except Exception as e:
            logger.error(f"An error occurred while deleting buffer for user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete buffer for user {user_id}: {e}"
            )


async def summarize_user_buffer_night():
    """
    Asynchronously create a night summary for the current date.
    
    This function generates a summary for the night period using the current date.
    It calls the create_summary function with a SummaryCreateRequest for the night period.
    Logs a debug message and handles any exceptions by logging an error and 
    raising an HTTP 500 Internal Server Error if the summary creation fails.
    """
    payload = SummaryCreateRequest(
        period="night",
        date=datetime.now().strftime("%Y-%m-%d")
    )

    try: 
        logger.debug(f"Creating night summary for date: {payload.date}")
        summaries = await create_summary(payload)
        logger.debug(f"Deleting user buffer for night summary for date: {payload.date}")
        await delete_user_buffer_from_summaries(summaries)

    except Exception as e:
        logger.error(f"Failed to trigger summarize_user_buffer_night(): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger summarize_user_buffer_night()"
        )


async def summarize_user_buffer_morning():
    """
    Asynchronously create a morning summary for the current date.
    
    This function generates a summary for the morning period using the current date.
    It calls the create_summary function with a SummaryCreateRequest for the morning period.
    Logs a debug message and handles any exceptions by logging an error and 
    raising an HTTP 500 Internal Server Error if the summary creation fails.
    """
    payload = SummaryCreateRequest(
        period="morning",
        date=datetime.now().strftime("%Y-%m-%d")
    )

    try: 
        logger.debug(f"Creating morning summary for date: {payload.date}")
        summaries = await create_summary(payload)
        logger.debug(f"Deleting user buffer for morning summary for date: {payload.date}")
        await delete_user_buffer_from_summaries(summaries)

    except Exception as e:
        logger.error(f"Failed to trigger summarize_user_buffer_morning(): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger summarize_user_buffer_morning()"
        )


async def summarize_user_buffer_afternoon():
    """
    Asynchronously create an afternoon summary for the current date.
    
    This function generates a summary for the afternoon period using the current date.
    It calls the create_summary function with a SummaryCreateRequest for the afternoon period.
    Logs a debug message and handles any exceptions by logging an error and 
    raising an HTTP 500 Internal Server Error if the summary creation fails.
    """
    payload = SummaryCreateRequest(
        period="afternoon",
        date=datetime.now().strftime("%Y-%m-%d")
    )

    try: 
        logger.debug(f"Creating afternoon summary for date: {payload.date}")
        summaries = await create_summary(payload)
        logger.debug(f"Deleting user buffer for afternoon summary for date: {payload.date}")
        await delete_user_buffer_from_summaries(summaries)

    except Exception as e:
        logger.error(f"Failed to trigger summarize_user_buffer_afternoon(): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger summarize_user_buffer_afternoon()"
        )


async def summarize_user_buffer_evening():
    """
    Asynchronously create an evening summary and daily summary for the previous day.
    
    This function performs two key tasks:
    1. Generates an evening summary for the previous day using the create_summary function.
    2. Creates a daily summary for the previous day using the create_daily_summary function.
    
    The function handles potential exceptions for both summary creation processes by logging errors
    and raising an HTTP 500 Internal Server Error if either summary fails to generate.
    
    Note: The function is designed to run at the end of the day, creating summaries for the previous day.
    Additional logic for weekly and monthly summary creation is planned but not yet implemented.
    """
    payload = SummaryCreateRequest(
        period="evening",
        date=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    )

    try: 
        logger.debug(f"Creating evening summary for date: {payload.date}")
        summaries = await create_summary(payload)
        logger.debug(f"Deleting user buffer for evening summary for date: {payload.date}")
        await delete_user_buffer_from_summaries(summaries)

    except Exception as e:
        logger.error(f"Failed to trigger summarize_user_buffer_evening(): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger summarize_user_buffer_evening()"
        )
    
    # next, create the summary for the day
    try:
       payload = SummaryCreateRequest(
            period="daily",
            date=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        )
       await create_daily_summary(payload)
       logger.debug(f"Creating daily summary for date: {payload.date}")

    except Exception as e:
        logger.error(f"Failed to trigger summarize_user_buffer_evening(): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger summarize_user_buffer_evening()"
        )
    
    # check to see if the day of the week is currently monday. this means a new week has started.
    # if it has, create the weekly summary.
    if datetime.now().weekday() == 0:
        try:
            payload = SummaryCreateRequest(
                period="weekly",
                date=(datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            )
            await create_weekly_summary(payload)
            logger.debug(f"Creating weekly summary for date: {payload.date}")

        except Exception as e:
            logger.error(f"Failed to trigger summarize_user_buffer_evening(): {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to trigger summarize_user_buffer_evening()"
            )

    # check to see if the date of the month is the 1st. this means a new month has started.
    if datetime.now().day == 1:
        try:
            payload = SummaryCreateRequest(
                period="monthly",
                date=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            )
            await create_monthly_summary(payload)
            logger.debug(f"Creating monthly summary for date: {payload.date}")

        except Exception as e:
            logger.error(f"Failed to trigger summarize_user_buffer_evening(): {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to trigger summarize_user_buffer_evening()"
            )



"""
create this job with:

import httpx

night_job_request = {
    "external_url": "http://brain:4207/scheduler/callback",
    "trigger": "cron",
    "hour": 6,
    "minute": 0,
    "metadata": {
        "function": "summarize_user_buffer_night"
    }
}

morning_job_request = {
    "external_url": "http://brain:4207/scheduler/callback",
    "trigger": "cron",
    "hour": 12,
    "minute": 0,
    "metadata": {
        "function": "summarize_user_buffer_morning"
    }
}

afternoon_job_request = {
    "external_url": "http://brain:4207/scheduler/callback",
    "trigger": "cron",
    "hour": 18,
    "minute": 0,
    "metadata": {
        "function": "summarize_user_buffer_afternoon"
    }
}

evening_job_request = {
    "external_url": "http://brain:4207/scheduler/callback",
    "trigger": "cron",
    "hour": 0,
    "minute": 0,
    "metadata": {
        "function": "summarize_user_buffer_evening"
    }
}

response = await httpx.post("http://brain:4207/scheduler/job", json=job_request)
"""