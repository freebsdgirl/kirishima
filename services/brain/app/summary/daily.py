"""
This module provides an API endpoint for creating daily summaries by aggregating period-specific summaries
(night, morning, afternoon, evening) for each user on a given date.
Main Features:
- Fetches individual period summaries from ChromaDB for a specified date.
- Groups summaries by user and generates a consolidated daily summary using a proxy service.
- Stores the generated daily summary in ChromaDB.
- Deletes the original period-specific summaries after successful aggregation.
Dependencies:
- FastAPI for API routing and HTTP exception handling.
- httpx for asynchronous HTTP requests.
- Shared configuration and models for summary data structures and service discovery.
- Logging for debugging and error tracking.
Endpoint:
- POST /summary/combined/daily: Aggregates and creates daily summaries for users.
- HTTPException for invalid input, missing summaries, or errors during summary generation, storage, or deletion.
"""

from app.config import SUMMARY_DAILY_MAX_TOKENS

from shared.models.summary import SummaryCreateRequest, SummaryMetadata, Summary, CombinedSummaryRequest


from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from app.util import get_user_alias

import httpx
import json
import os

from fastapi import HTTPException, status, APIRouter
router = APIRouter()

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


@router.post("/summary/combined/daily", status_code=status.HTTP_201_CREATED)
async def create_daily_summary(request: SummaryCreateRequest):
    """
    Create a daily summary by aggregating summaries from different periods of the day for a specific user.

    This endpoint retrieves summaries for night, morning, afternoon, and evening periods for a given date,
    combines them for each unique user, and generates a consolidated daily summary. The process involves:
    1. Fetching individual summaries from ChromaDB
    2. Grouping summaries by user
    3. Generating a combined summary using the proxy service
    4. Storing the daily summary in ChromaDB
    5. Deleting the original period-specific summaries

    Args:
        request (SummaryCreateRequest): Request containing the date for daily summary generation

    Raises:
        HTTPException: For various error scenarios such as invalid period, no summaries found,
        or issues with summary generation and storage
    """
    # although period is passed as part of the request, we'll ignore it and just use daily.
    # get all summaries that match night, morning, afternoon, evening
    if request.period != "daily":
        logger.error(f"Invalid period specified: {request.period}. Expected 'daily'.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid period specified. Expected 'daily'."
        )

    logger.debug(f"Creating daily summary for date: {request.date}")

    try:
        summaries = []

        chromadb_port = os.getenv("CHROMADB_PORT", 4206)

        for summary_type in ["night", "morning", "afternoon", "evening"]:
            try:
                url = f"http://chromadb:{chromadb_port}/summary?type={summary_type}"

                url += f"&timestamp_begin={request.date}%2000:00:00&timestamp_end={request.date}%2023:59:59"

                async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    summaries.extend(response.json())

            except httpx.HTTPStatusError as e:
                if e.response.status_code == status.HTTP_404_NOT_FOUND:
                    logger.info(f"No {summary_type} summaries found for {request.date}, skipping.")
                    continue
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
        logger.debug(f"Creating summary for user {user_id} with summaries: {user_summaries}")

        payload = CombinedSummaryRequest(
            summaries=user_summaries,
            user_alias=await get_user_alias(user_id),
            max_tokens=SUMMARY_DAILY_MAX_TOKENS
        )

        proxy_port = os.getenv("PROXY_PORT", 4205)
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(f"http://proxy:{proxy_port}/summary/user/combined", json=payload.model_dump())
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
            summary_type="daily",
            timestamp_begin=payload.summaries[0].metadata.timestamp_begin,
            timestamp_end=payload.summaries[-1].metadata.timestamp_end
        )
        summary = Summary(
            content=summary['summary'],
            metadata=metadata
        )
        logger.debug(f"Summary created for user {user_id}: {summary}")

        chromadb_port = os.getenv("CHROMADB_PORT", 4206)

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(f"http://chromadb:{chromadb_port}/summary", json=summary.model_dump())
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

        # if the period is daily and the summary was written to chromadb, delete
        # the morning, evening, afternoon, and night summaries for that user id.
        for summary in user_summaries:
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                    response = await client.delete(f"http://chromadb:{chromadb_port}/summary/{summary['id']}")
                    response.raise_for_status()
                    logger.debug(f"Deleted summary {summary['id']} from chromadb")

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=f"Error deleting summary: {e.response.text}"
                )

            except Exception as e:
                logger.error(f"An error occurred while deleting summary: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete summary: {e}"
                )

    return {"message": "Daily summary created successfully."}