"""
This module provides functionality to create a daily summary by aggregating and summarizing all period summaries for a given date.

Functions:
    create_daily_summary(request: SummaryCreateRequest) -> List[dict]:
        Asynchronously creates a daily summary by:
            1. Loading configuration settings and environment variables.
            2. Retrieving all period summaries for the specified date.
            3. Constructing a prompt to generate a daily summary using an external language model API.
            4. Sending the prompt to the API and receiving the generated summary.
            5. Storing the generated daily summary in the ledger.
            6. Deleting the original period summaries to avoid duplication.
"""
from shared.models.ledger import SummaryCreateRequest, SummaryMetadata, Summary

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from datetime import datetime
from fastapi import HTTPException, status
from app.summary.post import _insert_summary
from app.summary.get import _get_summaries
from app.services.summary.delete import _delete_summary
from typing import List
import httpx
import json
import os
from shared.models.openai import OpenAICompletionRequest
from shared.prompt_loader import load_prompt

async def create_daily_summary(request: SummaryCreateRequest) -> List[dict]:
    """
    Asynchronously creates a daily summary by aggregating and summarizing all period summaries for a given date.

    This function performs the following steps:
    1. Loads configuration settings and environment variables.
    2. Retrieves all period summaries for the specified date.
    3. Constructs a prompt to generate a daily summary using an external language model API.
    4. Sends the prompt to the API and receives the generated summary.
    5. Stores the generated daily summary in the ledger.
    6. Deletes the original period summaries to avoid duplication.

    Args:
        request (SummaryCreateRequest): The request object containing the target date for the daily summary.

    Returns:
        List[dict]: A list containing the stored daily summary as a dictionary.

    Raises:
        HTTPException: If summaries cannot be retrieved, summarized, or stored.
    """
    logger.debug(f"Creating daily summary for date: {request.date}")
    with open('/app/config/config.json') as f:
        _config = json.load(f)
    timeout = _config["timeout"]
    daily_max_tokens = _config["summary"]["daily_max_tokens"] if "daily" in _config["summary"] else 512
    api_port = os.getenv("API_PORT", 4200)


    # Use internal function to fetch all period summaries for the date
    try:
        summaries = [s.model_dump() for s in _get_summaries(timestamp_begin=f"{request.date} 00:00:00", timestamp_end=f"{request.date} 23:59:59")]
    except Exception as e:
        logger.error(f"Failed to get summaries for {request.date}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve summaries: {e}")

    if not summaries:
        logger.warning("No summaries found for the specified period.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No summaries found for the specified period."
        )

    # Build prompt for daily summary
    def format_timestamp(ts: str) -> str:
        dt = datetime.fromisoformat(ts.replace("Z", ""))
        return dt.strftime("%A, %B %d")
    
    # Add formatted_date to each summary for template
    formatted_summaries = []
    for summary in summaries:
        summary_dict = summary.copy()
        summary_dict['formatted_date'] = format_timestamp(summary["metadata"]["timestamp_begin"])
        formatted_summaries.append(summary_dict)
    
    prompt = load_prompt("ledger", "summary", "daily", 
                        summaries=formatted_summaries, 
                        max_tokens=daily_max_tokens)
    summary_req = OpenAICompletionRequest(
        model="gpt-4.1",
        prompt=prompt,
        max_tokens=daily_max_tokens*2,
        temperature=0.7,
        n=1,
        provider="openai"
    )
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"http://api:{api_port}/v1/completions",
                json=summary_req.model_dump()
            )
            response.raise_for_status()
        summary_data = response.json()
        summary_text = summary_data['choices'][0]['content']
    except Exception as e:
        logger.error(f"Failed to summarize daily for date {request.date}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to summarize daily: {e}"
        )
    # Compose metadata (no user_id)
    metadata = SummaryMetadata(
        summary_type="daily",
        timestamp_begin=summaries[0]["metadata"]["timestamp_begin"],
        timestamp_end=summaries[-1]["metadata"]["timestamp_end"]
    )
    summary_obj = Summary(content=summary_text, metadata=metadata)
    # Store in ledger
    results = []
    try:
        result = _insert_summary(summary_obj)
        results.append(result.model_dump())
    except Exception as e:
        logger.error(f"Failed to write daily summary to ledger: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write daily summary: {e}"
        )
    # Delete original period summaries, skipping duplicates
    deleted_ids = set()
    for s in summaries:
        summary_id = s['id']
        if summary_id in deleted_ids:
            continue
        try:
            _delete_summary(id=summary_id)
            deleted_ids.add(summary_id)
        except Exception as e:
            logger.warning(f"Failed to delete period summary {summary_id}: {e}")
    return results