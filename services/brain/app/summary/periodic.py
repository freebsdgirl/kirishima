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

from shared.models.summary import SummaryCreateRequest, SummaryMetadata, Summary, SummaryRequest, CombinedSummaryRequest

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from app.util import get_user_alias

from typing import List
import httpx
import json

from fastapi import HTTPException, status, APIRouter
router = APIRouter()

import os

from transformers import AutoTokenizer
from shared.models.ledger import CanonicalUserMessage

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


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
    try:
        ledger_port = os.getenv("LEDGER_PORT", 4203)
        response = httpx.get(f"http://ledger:{ledger_port}/active", timeout=TIMEOUT)
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
            response = httpx.get(f"http://ledger:{ledger_port}/user/{user_id}/messages", params=params, timeout=TIMEOUT)
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

        # Chunk messages into 4096-token chunks using AutoTokenizer (gpt2)
        tokenizer = AutoTokenizer.from_pretrained("gpt2")
        max_tokens = 4096

        # Ensure all messages are CanonicalUserMessage
        canon_msgs = [CanonicalUserMessage.model_validate(m) if not isinstance(m, CanonicalUserMessage) else m for m in messages]

        def chunk_messages(messages, max_tokens):
            chunks = []
            current_chunk = []
            current_tokens = 0
            for msg in messages:
                content = msg.content
                tokens = len(tokenizer.encode(content))
                if current_tokens + tokens > max_tokens and current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_tokens = 0
                current_chunk.append(msg)
                current_tokens += tokens
            if current_chunk:
                chunks.append(current_chunk)
            return chunks

        message_chunks = chunk_messages(canon_msgs, max_tokens)
        summaries = []

        proxy_port = os.getenv("PROXY_PORT", 4205)
        for chunk in message_chunks:
            payload = SummaryRequest(
                messages=chunk,
                user_alias=alias,
                max_tokens=SUMMARY_PERIODIC_MAX_TOKENS
            )
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                    response = await client.post(f"http://proxy:{proxy_port}/summary/user", json=payload.model_dump())
                    response.raise_for_status()
                summary_data = response.json()
                metadata = SummaryMetadata(
                    user_id=user_id,
                    summary_type=request.period,
                    timestamp_begin=chunk[0].created_at,
                    timestamp_end=chunk[-1].created_at
                )
                summaries.append(Summary(content=summary_data['summary'], metadata=metadata))
            except Exception as e:
                logger.error(f"Failed to summarize chunk: {e}")
                continue

        # If more than 1 Summary is created, combine them
        if len(summaries) > 1:
            combined_payload = CombinedSummaryRequest(
                summaries=summaries,
                user_alias=alias,
                max_tokens=SUMMARY_PERIODIC_MAX_TOKENS
            )
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                    response = await client.post(f"http://proxy:{proxy_port}/summary/user/combined", json=combined_payload.model_dump())
                    response.raise_for_status()
                summary_data = response.json()
                metadata = SummaryMetadata(
                    user_id=user_id,
                    summary_type=request.period,
                    timestamp_begin=summaries[0].metadata.timestamp_begin,
                    timestamp_end=summaries[-1].metadata.timestamp_end
                )
                final_summary = Summary(content=summary_data['summary'], metadata=metadata)
            except Exception as e:
                logger.error(f"Failed to combine summaries: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to combine summaries: {e}"
                )
        else:
            final_summary = summaries[0]

        logger.debug(f"Final summary for user {user_id}: {final_summary}")

        try:
            chromadb_port = os.getenv("CHROMADB_PORT", 4206)
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(f"http://chromadb:{chromadb_port}/summary", json=final_summary.model_dump())
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

