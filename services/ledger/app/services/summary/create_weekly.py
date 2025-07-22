"""
Creates a weekly summary by aggregating daily summaries for a single user over a week (Monday-Sunday).

Args:
    request (SummaryCreateRequest): The request object containing the date (must be a Monday) and other summary parameters.

Returns:
    List[dict]: A list containing the created weekly summary as a dictionary. Returns an empty list if the date is not a Monday or if no daily summaries are found.

Raises:
    HTTPException: If the date format is invalid, if daily summaries cannot be retrieved, if the weekly summary cannot be generated, or if the summary cannot be written to the ledger.

Process:
    - Validates that the provided date is a Monday in 'YYYY-MM-DD' format.
    - Loads configuration and environment variables.
    - Fetches all daily summaries for the week (Monday-Sunday).
    - Constructs a prompt for the language model to generate a weekly summary.
    - Calls the OpenAI API (or compatible provider) to generate the summary.
    - Stores the generated weekly summary in the ledger.
"""
from shared.models.ledger import SummaryCreateRequest, SummaryMetadata, Summary
from shared.models.openai import OpenAICompletionRequest
from shared.prompt_loader import load_prompt

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.services.summary.insert import _insert_summary
from app.services.summary.get import _get_summaries

from datetime import datetime, timedelta
from fastapi import HTTPException, status
from typing import List
import httpx
import json
import os


async def _create_weekly_summary(request: SummaryCreateRequest) -> List[dict]:
    """
    Asynchronously creates a weekly summary for a user by aggregating daily summaries over a specified week (Monday to Sunday).

    Args:
        request (SummaryCreateRequest): The request object containing the date (must be a Monday) and other summary creation parameters.

    Returns:
        List[dict]: A list containing the created weekly summary as a dictionary. Returns an empty list if the date is not a Monday or if no daily summaries are found.

    Raises:
        HTTPException: If the input date is invalid, if daily summaries cannot be retrieved, if the weekly summary cannot be generated, or if the summary cannot be written to the ledger.

    Process:
        - Validates the input date and ensures it is a Monday.
        - Loads configuration parameters from a JSON file.
        - Fetches daily summaries for the week.
        - Constructs a prompt for summarization using the daily summaries.
        - Calls an internal API to generate the weekly summary using an LLM.
        - Stores the generated summary in the ledger.
        - Returns the result as a list of dictionaries.
    """
    # Weekly summary: aggregate daily summaries for a single user for a week (Monday-Sunday)
    try:
        request_date = datetime.strptime(request.date, "%Y-%m-%d")
    except ValueError:
        logger.error(f"Invalid date specified: {request.date}. Expected 'YYYY-MM-DD' format.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date specified. Expected 'YYYY-MM-DD' format."
        )
    # Ensure the date is a Monday
    if request_date.weekday() != 0:
        return []
    logger.debug(f"Creating weekly summary for date: {request.date}")
    with open('/app/config/config.json') as f:
        _config = json.load(f)
    timeout = _config["timeout"]
    weekly_max_tokens = _config["summary"].get("weekly_max_tokens", 1024)
    api_port = os.getenv("API_PORT", 4200)
    timestamp_begin = request_date.strftime("%Y-%m-%d 00:00:00")
    sunday = request_date + timedelta(days=6)
    timestamp_end = sunday.strftime("%Y-%m-%d 23:59:59")
    # Use internal function to fetch daily summaries for the week
    try:
        summaries = [s.model_dump() for s in _get_summaries(period="daily", timestamp_begin=timestamp_begin, timestamp_end=timestamp_end)]
    except Exception as e:
        logger.error(f"Failed to get daily summaries for week {request.date}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve summaries: {e}")
    if not summaries:
        logger.warning("No summaries found for the specified period.")
        return []
    # Build prompt for weekly summary
    def format_timestamp(ts: str) -> str:
        dt = datetime.fromisoformat(ts.replace("Z", ""))
        return dt.strftime("%A, %B %d")
    
    # Add formatted_date to each summary for template
    formatted_summaries = []
    for summary in summaries:
        summary_dict = summary.copy()
        summary_dict['formatted_date'] = format_timestamp(summary["metadata"]["timestamp_begin"])
        formatted_summaries.append(summary_dict)
    
    prompt = load_prompt("ledger", "summary", "weekly", 
                        summaries=formatted_summaries, 
                        max_tokens=weekly_max_tokens)
    summary_req = OpenAICompletionRequest(
        model="gpt-4.1",
        prompt=prompt,
        max_tokens=weekly_max_tokens,
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
        logger.error(f"Failed to summarize weekly for date {request.date}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to summarize weekly: {e}"
        )
    metadata = SummaryMetadata(
        summary_type="weekly",
        timestamp_begin=summaries[0]["metadata"]["timestamp_begin"],
        timestamp_end=summaries[-1]["metadata"]["timestamp_end"]
    )
    summary_obj = Summary(content=summary_text, metadata=metadata)
    results = []
    try:
        result = _insert_summary(summary_obj)
        results.append(result.model_dump())
    except Exception as e:
        logger.error(f"Failed to write weekly summary to ledger: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write weekly summary: {e}"
        )
    return results
