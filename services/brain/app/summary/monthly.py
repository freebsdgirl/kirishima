"""
This module provides an API endpoint for generating and storing monthly summaries for users by aggregating their daily summaries.
Functions:
    create_monthly_summary(request: SummaryCreateRequest):
        Handles POST requests to "/summary/combined/monthly". Validates the request, retrieves daily summaries for the specified month,
        generates a combined monthly summary for each user, and stores the results in ChromaDB. Raises HTTPException for invalid input,
        missing summaries, or processing errors.
"""

from app.config import SUMMARY_MONTHLY_MAX_TOKENS

from shared.models.summary import SummaryCreateRequest, SummaryMetadata, Summary, CombinedSummaryRequest

import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from app.util import get_user_alias

import httpx
from datetime import datetime
from calendar import monthrange
import json

from fastapi import HTTPException, status, APIRouter
router = APIRouter()

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


@router.post("/summary/combined/monthly", status_code=status.HTTP_201_CREATED)
async def create_monthly_summary(request: SummaryCreateRequest):
    """
    Create monthly summaries for users by aggregating their daily summaries.

    This endpoint processes a monthly summary request by:
    1. Validating the request period and date
    2. Retrieving daily summaries for the specified month
    3. Generating a combined summary for each unique user
    4. Storing the monthly summaries in ChromaDB

    Args:
        request (SummaryCreateRequest): Request containing the month and date for summary generation

    Returns:
        dict: A message indicating successful monthly summary creation

    Raises:
        HTTPException: For invalid requests, missing summaries, or processing errors
    """
    # although period is passed as part of the request, we'll ignore it and just use monthly.
    # construct our time constraints for search, then use this for timestamp_begin and timestamp_end
    # get all summaries that match daily
    if request.period != "monthly":
        logger.error(f"Invalid period specified: {request.period}. Expected 'monthly'.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid period specified. Expected 'monthly'."
        )
    
    # request.date is a string that matches "YYYY-MM-DD".
    try:
        request_date = datetime.strptime(request.date, "%Y-%m-%d")
    except ValueError:
        logger.error(f"Invalid date specified: {request.date}. Expected 'YYYY-MM-DD' format.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date specified. Expected 'YYYY-MM-DD' format."
        )

    logger.debug(f"Creating weekly summary for month: {request_date.month}")

    try:
        summaries = []

        chromadb_address, chromadb_port = shared.consul.get_service_address('chromadb')
    
        timestamp_begin = request_date.replace(day=1).strftime("%Y-%m-%d 00:00:00")
        last_day = monthrange(request_date.year, request_date.month)[1]
        timestamp_end = request_date.replace(day=last_day).strftime("%Y-%m-%d 23:59:59")

        url = f"http://{chromadb_address}:{chromadb_port}/summary?type=daily"
        url += f"&timestamp_begin={timestamp_begin}&timestamp_end={timestamp_end}"

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            summaries.extend(response.json())

    except httpx.HTTPStatusError as e:
        if e.response.status_code == status.HTTP_404_NOT_FOUND:
            logger.info(f"No daily summaries found for {request.date}, skipping.")
        else:
            logger.error(f"HTTP error from chromadb: {e.response.status_code} - {e.response.text}")
            raise

    except Exception as e:
        logger.error(f"Failed to contact chromadb to get a list of summaries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve summaries: {e}")

    if not summaries:
        logger.warning("No summaries found for the specified period.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No summaries found for the specified period."
        )

    # summmaries is a list of Summary objects.
    # determine a list of user_ids from these objects using metadata.user_id
    user_ids = set()
    for summary in summaries:
        user_ids.add(summary["metadata"]["user_id"])

    # step through each user id and take the summaries for that user id
    # and send it to the proxy service for re-summarization.
    for user_id in user_ids:
        user_summaries = [s for s in summaries if s["metadata"]["user_id"] == user_id]
        logger.debug(f"Creating monthly summary for user {user_id} with summaries: {user_summaries}")

        payload = CombinedSummaryRequest(
            summaries=user_summaries,
            user_alias=await get_user_alias(user_id),
            max_tokens=SUMMARY_MONTHLY_MAX_TOKENS
        )

        proxy_address, proxy_port = shared.consul.get_service_address('proxy')
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(f"http://{proxy_address}:{proxy_port}/summary/user/combined", json=payload.model_dump())
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Error creating summary: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"An error occurred while creating summary: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create summary: {e}"
            )
        

        summary = response.json()

        metadata = SummaryMetadata(
            user_id=user_id,
            summary_type="monthly",
            timestamp_begin=payload.summaries[0].metadata.timestamp_begin,
            timestamp_end=payload.summaries[-1].metadata.timestamp_end
        )
        summary = Summary(
            content=summary['summary'],
            metadata=metadata
        )
        logger.debug(f"Monthly summary created for user {user_id}: {summary}")

        # write the summary to chromadb for weekly
        chromadb_address, chromadb_port = shared.consul.get_service_address('chromadb')

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(f"http://{chromadb_address}:{chromadb_port}/summary", json=summary.model_dump())
                response.raise_for_status()

                summary = response.json()
                logger.debug(f"Summary written to chromadb: {summary['id']}")

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Error writing summary to chromadb: {e.response.text}"
            )

        except Exception as e:
            logger.error(f"An error occurred while writing summary to chromadb: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to write summary to chromadb: {e}"
            )

    return {"message": "Monthly summaries created successfully."}