"""
Creates a monthly summary by aggregating daily summaries for a single user over a specified month.

Args:
    request (SummaryCreateRequest): The request object containing the date (in 'YYYY-MM-DD' format) and other summary creation parameters.

Returns:
    List[dict]: A list containing the created monthly summary as a dictionary. Returns an empty list if the date is not the first of the month or if no daily summaries are found.

Raises:
    HTTPException: If the date format is invalid, if daily summaries cannot be retrieved, if the monthly summary cannot be generated, or if the summary cannot be written to the ledger.

Process:
    - Validates the input date and ensures it is the first day of the month.
    - Rolls back to the last day of the previous month to determine the month to summarize.
    - Loads configuration and environment variables.
    - Fetches all daily summaries for the target month.
    - Constructs a prompt for the language model to generate a monthly summary.
    - Calls an external API to generate the summary using the prompt.
    - Inserts the generated summary into the ledger.
    - Returns the result as a list of dictionaries.
"""
from shared.models.ledger import SummaryCreateRequest, SummaryMetadata, Summary

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from datetime import datetime, timedelta
from fastapi import HTTPException, status
from app.summary.post import _insert_summary
from app.summary.get import _get_summaries
from typing import List
import httpx
import json
import os
from shared.models.openai import OpenAICompletionRequest

async def create_monthly_summary(request: SummaryCreateRequest) -> List[dict]:
    """
    Asynchronously creates a monthly summary by aggregating daily summaries for a single user over a specified month.

    Args:
        request (SummaryCreateRequest): The request object containing the date (in 'YYYY-MM-DD' format) and other relevant parameters.

    Returns:
        List[dict]: A list containing the created monthly summary as a dictionary. Returns an empty list if the date is not the first of the month or if no summaries are found.

    Raises:
        HTTPException: If the input date is invalid, if daily summaries cannot be retrieved, if the monthly summary cannot be generated, or if the summary cannot be written to the ledger.

    Process Overview:
        - Validates the input date and ensures it is the first day of the month.
        - Loads configuration and environment variables.
        - Determines the time range for the month.
        - Fetches daily summaries for the specified month.
        - Constructs a prompt for summarization using the daily summaries.
        - Calls an external API to generate the monthly summary.
        - Stores the generated summary in the ledger.
        - Returns the result as a list of dictionaries.
    """
    # Monthly summary: aggregate daily summaries for a single user for a month
    try:
        request_date = datetime.strptime(request.date, "%Y-%m-%d")
    except ValueError:
        logger.error(f"Invalid date specified: {request.date}. Expected 'YYYY-MM-DD' format.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date specified. Expected 'YYYY-MM-DD' format."
        )
    # If the day is the 1st, roll back to the last day of the previous month
    if request_date.day != 1:
        return []
    request_date = request_date - timedelta(days=1)
    from calendar import monthrange
    logger.debug(f"Creating monthly summary for date: {request.date}")
    with open('/app/config/config.json') as f:
        _config = json.load(f)
    timeout = _config["timeout"]
    monthly_max_tokens = _config["summary"].get("monthly_max_tokens", 2048)
    api_port = os.getenv("API_PORT", 4200)
    timestamp_begin = request_date.replace(day=1).strftime("%Y-%m-%d 00:00:00")
    last_day = monthrange(request_date.year, request_date.month)[1]
    timestamp_end = request_date.replace(day=last_day).strftime("%Y-%m-%d 23:59:59")
    # Use internal function to fetch daily summaries for the month
    try:
        summaries = [s.model_dump() for s in _get_summaries(period="daily", timestamp_begin=timestamp_begin, timestamp_end=timestamp_end)]
    except Exception as e:
        logger.error(f"Failed to get daily summaries for month {request.date}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve summaries: {e}")
    if not summaries:
        logger.warning("No summaries found for the specified period.")
        return []
    # Build prompt for monthly summary
    def format_timestamp(ts: str) -> str:
        dt = datetime.fromisoformat(ts.replace("Z", ""))
        return dt.strftime("%A, %B %d")
    prompt = f"""
### Task: Using the provided summaries, generate a single summary that reflects how events unfolded over the month.

### Summaries
"""
    for summary in summaries:
        date_str = format_timestamp(summary["metadata"]["timestamp_begin"])
        prompt += f"[{summary['metadata']['summary_type'].upper()} – {date_str}] {summary['content']}\n"
    prompt += f"""

### Instructions
- Organize the summary chronologically. Use time indicators like "Early in the month…", "Mid-month…", "By the end of the month…", etc.
- Emphasize key actions and decisions.
- Maintain a coherent narrative flow.
- Use dense paragraphs. Do not use formatting.
- Your response must not exceed {monthly_max_tokens} tokens.
"""
    summary_req = OpenAICompletionRequest(
        model="gpt-4.1",
        prompt=prompt,
        max_tokens=monthly_max_tokens*2,
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
        logger.error(f"Failed to summarize monthly for date {request.date}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to summarize monthly: {e}"
        )
    metadata = SummaryMetadata(
        summary_type="monthly",
        timestamp_begin=summaries[0]["metadata"]["timestamp_begin"],
        timestamp_end=summaries[-1]["metadata"]["timestamp_end"]
    )
    summary_obj = Summary(content=summary_text, metadata=metadata)
    results = []
    try:
        result = _insert_summary(summary_obj)
        results.append(result.model_dump())
    except Exception as e:
        logger.error(f"Failed to write monthly summary to ledger: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write monthly summary: {e}"
        )
    return results

