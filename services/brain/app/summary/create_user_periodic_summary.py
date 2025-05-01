"""
This module provides an API endpoint for creating periodic summaries for active users.
The main functionality includes:
- Retrieving active user IDs from the ledger service.
- Fetching user messages for a specified period and date.
- Generating summaries for each user using the proxy service.
- Storing the generated summaries in ChromaDB.
Modules and dependencies:
- FastAPI for API routing and HTTP exception handling.
- httpx for making HTTP requests to internal services.
- shared.consul for service discovery.
- shared.models for data models related to summaries and ledger requests.
- app.util for utility functions such as user alias retrieval.
- Logging for error tracking and debugging.
Endpoint:
- POST /summary/create: Triggers the summary creation process for all active users for a given period and date.
- HTTPException: For invalid input, service communication errors, or summary generation/storage failures.
"""

from app.config import SUMMARY_PERIODIC_MAX_TOKENS

from shared.config import TIMEOUT

from shared.models.summary import SummaryCreateRequest, SummaryMetadata, Summary
from shared.models.ledger import SummaryRequest

import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from app.util import get_user_alias

from typing import List
import httpx

from fastapi import HTTPException, status, APIRouter
router = APIRouter()


@router.post("/summary/create", status_code=status.HTTP_201_CREATED, response_model=List[Summary])
async def create_summary(request: SummaryCreateRequest) -> List[Summary]:
    """
    Create periodic user summaries by fetching active users, retrieving their messages, and generating summaries.

    This endpoint handles the creation of summaries for active users during a specified time period (morning, afternoon, evening, night).
    It performs the following key steps:
    - Retrieves active user IDs from the ledger service
    - Fetches messages for each user
    - Generates a summary using the proxy service
    - Stores the summary in ChromaDB

    Args:
        request (SummaryCreateRequest): Request containing summary creation parameters like period and date

    Returns:
        dict: Summary creation result or error details

    Raises:
        HTTPException: For invalid periods, service communication errors, or summary generation failures
    """
    logger.debug(f"Creating periodic summary for period: {request.period} and date: {request.date}")
    # connect to the ledger service to get a list of user_ids
    ledger_address, ledger_port = shared.consul.get_service_address('ledger')
    try:
        response = httpx.get(f"http://{ledger_address}:{ledger_port}/active", timeout=TIMEOUT)
        response.raise_for_status()

    except Exception as e:
        logger.error(f"Failed to trigger create_summary(): {e}")
    
    user_ids = response.json()
    logger.debug(f"Active user IDs: {user_ids}")

    # if nothing is returned, there's no one to summarize.
    if not user_ids:
        return {"message": "No active users found."}

    summaries_created = []
    
    # for each user_id, get the buffer
    for user_id in user_ids:
        params = {}
        params["period"] = request.period
        params["date"] = request.date

        if params["period"] not in ["night", "morning", "afternoon", "evening"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid period. Must be one of: night, morning, afternoon, evening."
            )

        try:
            response = httpx.get(f"http://{ledger_address}:{ledger_port}/user/{user_id}/messages", params=params, timeout=TIMEOUT)
            response.raise_for_status()
            messages = response.json()
        except Exception as e:
            logger.error(f"Failed to get user messages: {e}")
            continue

        # if no user ids are listed
        if not messages:
            logger.warning(f"No messages found for user {user_id} for period {request.period} on date {request.date}")
            continue

        # get the alias for the user
        alias = await get_user_alias(user_id)

        logger.debug(f"Creating summary for user {user_id} with alias {alias} and messages: {messages}")
        payload = SummaryRequest(
            messages=messages,
            user_alias=alias,
            max_tokens=SUMMARY_PERIODIC_MAX_TOKENS
        )

        try:
            proxy_address, proxy_port = shared.consul.get_service_address('proxy')
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(f"http://{proxy_address}:{proxy_port}/summary/user", json=payload.model_dump())
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
        logger.debug(f"Summary created for user {user_id}: {summary}")

        metadata = SummaryMetadata(
            user_id=user_id,
            summary_type=request.period,
            timestamp_begin=payload.messages[0].created_at,
            timestamp_end=payload.messages[-1].created_at
        )

        try:
            summary = Summary(
                content=summary['summary'],
                metadata=metadata
            )
            logger.debug(f"Summary object created: {summary}")

            chromadb_address, chromadb_port = shared.consul.get_service_address('chromadb')
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(f"http://{chromadb_address}:{chromadb_port}/summary", json=summary.model_dump())
                response.raise_for_status()
            
            summaries_created.append(response.json())

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Error creating summary: {e.response.text}"
            )

        except Exception as e:
            logger.error(f"Failed to create summary: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create summary: {e}"
            )
    

    return summaries_created

