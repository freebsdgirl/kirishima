"""
This module provides FastAPI endpoints and supporting functions for generating user conversation summaries
over various time periods (periodic, daily, weekly, monthly) in a chat application.
Key Features:
-------------
- Generates summaries for active users based on their chat messages, grouped by specified periods:
    - Periodic: "night", "morning", "afternoon", "evening"
    - Daily: Aggregates all period summaries for a day
    - Weekly: Aggregates daily summaries for a week (Monday-Sunday)
    - Monthly: Aggregates daily summaries for a month
- Utilizes external services for:
    - Fetching active users and their messages (ledger service)
    - Generating summaries via LLM API (proxy service)
    - Storing and retrieving summaries (ChromaDB)
- Handles chunking of messages to fit model token limits and combines multiple summaries when needed
- Provides robust error handling and logging for service communication and summary generation failures
Endpoints:
----------
- POST /summary: Accepts a summary creation request and generates summaries for the specified periods
Main Functions:
---------------
- generate_summary: Orchestrates summary generation for requested periods
- create_periodic_summary: Generates summaries for each active user for a specific period
- create_daily_summary: Aggregates period summaries into a daily summary per user
- create_weekly_summary: Aggregates daily summaries into a weekly summary per user
- create_monthly_summary: Aggregates daily summaries into a monthly summary per user
Dependencies:
-------------
- FastAPI, httpx, transformers, shared.models, shared.log_config, app.util
Environment Variables:
----------------------
- LEDGER_PORT, API_PORT, CHROMADB_PORT, PROXY_PORT
Configuration:
--------------
- Reads settings from /app/config/config.json (timeout, summary token limits, etc.)
"""
from shared.models.ledger import SummaryCreateRequest, SummaryMetadata, Summary, SummaryRequest, CombinedSummaryRequest

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from datetime import datetime, timedelta
from fastapi import HTTPException, status, APIRouter
from app.util import get_user_alias
from typing import List, Union
import httpx
import json
import os
from transformers import AutoTokenizer
from shared.models.ledger import CanonicalUserMessage


router = APIRouter()

VALID_PERIODS = ["night", "morning", "afternoon", "evening"]
ALL_PERIODS = VALID_PERIODS + ["daily", "weekly", "monthly"]

@router.post("/summary")
async def generate_summary(request: SummaryCreateRequest) -> List[dict]:
    # Accept period as List[str] (enforced in model)
    periods = request.period if isinstance(request.period, list) else [request.period]
    results = []
    for period in periods:
        if period in VALID_PERIODS:
            req = request.copy(update={"period": period})
            results.extend(await create_periodic_summary(req))
        elif period == "daily":
            req = request.copy(update={"period": period})
            results.extend(await create_daily_summary(req))
        elif period == "weekly":
            req = request.copy(update={"period": period})
            results.extend(await create_weekly_summary(req))
        elif period == "monthly":
            req = request.copy(update={"period": period})
            results.extend(await create_monthly_summary(req))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid period: {period}"
            )
    return results

async def create_periodic_summary(request: SummaryCreateRequest) -> List[dict]:
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
        List[dict]: List of summary creation results or error details

    Raises:
        HTTPException: For invalid periods, service communication errors, or summary generation failures
    """
    logger.debug(f"Creating periodic summary for period: {request.period} and date: {request.date}")

    with open('/app/config/config.json') as f:
        _config = json.load(f)

    timeout = _config["timeout"]
    user_id = _config.get("user_id")
    summaries_created = []
    params = {}
    params["period"] = request.period
    params["date"] = request.date

    if params["period"] not in VALID_PERIODS:
        logger.error(f"Invalid period '{params['period']}' for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid period. Must be one of: {', '.join(VALID_PERIODS)}."
        )

    if request.period == "evening" and not request.date:
        # evening is a special case, we need to get the previous day
        params["date"] = (datetime.strptime(request.date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

    # get the messages for the user
    ledger_port = os.getenv("LEDGER_PORT", 4203)
    try:
        response = httpx.get(f"http://ledger:{ledger_port}/user/{user_id}/messages", params=params, timeout=timeout)
        response.raise_for_status()
        messages = response.json()
    except Exception as e:
        logger.error(f"Failed to get user messages for user {user_id}, period {params['period']}, date {params['date']}: {e}")
        return []

    # if no messages are listed
    if not messages:
        logger.warning(f"No messages found for user {user_id} for period {request.period} on date {request.date}")
        return []

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

    periodic_max_tokens = _config["summary"]["periodic_max_tokens"] or 256
    api_port = os.getenv("API_PORT", 4200)
    for chunk in message_chunks:
        # Prompt construction (moved from proxy/app/summary.py)
        user_label = alias or "Randi"
        assistant_label = "Kirishima"
        lines = []
        for msg in chunk:
            if hasattr(msg, 'role') and msg.role == "user":
                lines.append(f"{user_label}: {msg.content}")
            elif hasattr(msg, 'role') and msg.role == "assistant":
                lines.append(f"{assistant_label}: {msg.content}")
        conversation_str = "\n".join(lines)

        logger.debug(f"Conversation string for summary: {conversation_str}")

        prompt = f'''
### Task: Summarize the following conversation between Randi (the user) and Kirishima (the assistant) in a clear and concise manner.



### Conversation

{conversation_str}



### Instructions

- The summary should capture the main points of the conversation.
- The summary must be no more than {periodic_max_tokens} tokens in length.
- The summary should be a single paragraph.
- Prioritize outcomes, decisions, or action items over small talk.
'''

        from shared.models.openai import OpenAICompletionRequest
        summary_req = OpenAICompletionRequest(
            model="gpt-4.1",  # or use from config if needed
            prompt=prompt,
            max_tokens=periodic_max_tokens,
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
            metadata = SummaryMetadata(
                summary_type=request.period,
                timestamp_begin=chunk[0].created_at,
                timestamp_end=chunk[-1].created_at
            )
            summaries.append(Summary(content=summary_text, metadata=metadata))
        except Exception as e:
            logger.error(f"Failed to summarize chunk for period {params['period']}, date {params['date']}: {e}")
            continue

    # If more than 1 Summary is created, combine them
    if len(summaries) > 1:
        # Build combined summary prompt (from proxy/app/summary.py)
        def format_timestamp(ts: str) -> str:
            dt = datetime.fromisoformat(ts.replace("Z", ""))
            return dt.strftime("%A, %B %d")
        combined_prompt = f"""
### Task: Using the provided summaries, generate a single summary that reflects how events unfolded over time.

### Summaries"""
        for summary in summaries:
            date_str = format_timestamp(summary.metadata.timestamp_begin)
            combined_prompt += f"[{summary.metadata.summary_type.upper()} – {date_str}] {summary.content}\n"
        combined_prompt += f"""

### Instructions
- Organize the summary chronologically. 
- Your response cannot exceed {periodic_max_tokens} tokens.
"""
        combined_req = OpenAICompletionRequest(
            model="gpt-4.1",
            prompt=combined_prompt,
            max_tokens=periodic_max_tokens,
            temperature=0.3,
            n=1,
            provider="openai"
        )
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"http://api:{api_port}/v1/completions",
                    json=combined_req.model_dump()
                )
                response.raise_for_status()
            combined_data = response.json()
            combined_text = combined_data['choices'][0]['content']
            metadata = SummaryMetadata(
                summary_type=request.period,
                timestamp_begin=summaries[0].metadata.timestamp_begin,
                timestamp_end=summaries[-1].metadata.timestamp_end
            )
            final_summary = Summary(content=combined_text, metadata=metadata)
        except Exception as e:
            logger.error(f"Failed to combine summaries for period {params['period']}, date {params['date']}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to combine summaries: {e}"
            )
    else:
        final_summary = summaries[0]

    logger.debug(f"Final summary: {final_summary}")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"http://ledger:{ledger_port}/summary", json=final_summary.model_dump())
            response.raise_for_status()
        summaries_created.append(response.json())

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred for period {params['period']}, date {params['date']}: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error creating summary: {e.response.text}"
        )

    except Exception as e:
        logger.error(f"Failed to create summary for period {params['period']}, date {params['date']}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create summary: {e}"
        )

    return summaries_created

async def create_daily_summary(request: SummaryCreateRequest) -> List[dict]:
    logger.debug(f"Creating daily summary for date: {request.date}")
    with open('/app/config/config.json') as f:
        _config = json.load(f)
    timeout = _config["timeout"]
    daily_max_tokens = _config["summary"]["daily_max_tokens"] if "daily" in _config["summary"] else 512
    api_port = os.getenv("API_PORT", 4200)
    ledger_port = os.getenv("LEDGER_PORT", 4203)

    # Fetch all period summaries for the date in a single request
    url = f"http://ledger:{ledger_port}/summary?timestamp_begin={request.date}%2000:00:00&timestamp_end={request.date}%2023:59:59"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            summaries = response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == status.HTTP_404_NOT_FOUND:
            logger.info(f"No summaries found for {request.date}, skipping.")
            summaries = []
        else:
            logger.error(f"HTTP error from ledger: {e.response.status_code} - {e.response.text}")
            raise
    except Exception as e:
        logger.error(f"Failed to contact ledger to get a list of summaries: {e}")
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
    prompt = f"""
### Task: Using the provided summaries, generate a single summary that reflects how events unfolded over time.

### Summaries
"""
    for summary in summaries:
        date_str = format_timestamp(summary["metadata"]["timestamp_begin"])
        prompt += f"[{summary['metadata']['summary_type'].upper()} – {date_str}] {summary['content']}\n"
    prompt += f"""

### Instructions
- Organize the summary chronologically. Use time indicators like "In the morning", "In the afternoon", "In the evening" when appropriate.
- Emphasize key actions and decisions..
- Do not use formatting. Use dense paragraphs for summaries.
- The summary cannot exceed {daily_max_tokens} tokens.
"""
    from shared.models.openai import OpenAICompletionRequest
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
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"http://ledger:{ledger_port}/summary", json=summary_obj.model_dump())
            if response.status_code >= 400:
                logger.error(f"Ledger error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Ledger error: {response.text}"
                )
            response.raise_for_status()
            results.append(response.json())
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
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.delete(f"http://ledger:{ledger_port}/summary?id={summary_id}")
                response.raise_for_status()
            deleted_ids.add(summary_id)
        except Exception as e:
            logger.warning(f"Failed to delete period summary {summary_id}: {e}")
    return results

async def create_weekly_summary(request: SummaryCreateRequest) -> List[dict]:
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
    ledger_port = os.getenv("LEDGER_PORT", 4203)
    api_port = os.getenv("API_PORT", 4200)
    user_id = _config.get("user_id")
    timestamp_begin = request_date.strftime("%Y-%m-%d 00:00:00")
    sunday = request_date + timedelta(days=6)
    timestamp_end = sunday.strftime("%Y-%m-%d 23:59:59")
    url = f"http://ledger:{ledger_port}/summary?type=daily"
    url += f"&timestamp_begin={timestamp_begin}&timestamp_end={timestamp_end}"
    try:
        summaries = []
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            summaries.extend(response.json())
    except httpx.HTTPStatusError as e:
        if e.response.status_code == status.HTTP_404_NOT_FOUND:
            logger.info(f"No daily summaries found for {request.date}, skipping.")
            return []
        else:
            logger.error(f"HTTP error from ledger: {e.response.status_code} - {e.response.text}")
            raise
    except Exception as e:
        logger.error(f"Failed to contact ledger to get a list of summaries: {e}")
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
    prompt = f"""
### Task: Using the provided summaries, generate a single summary that reflects how events unfolded over the week.

### Summaries
"""
    for summary in summaries:
        date_str = format_timestamp(summary["metadata"]["timestamp_begin"])
        prompt += f"[{summary['metadata']['summary_type'].upper()} – {date_str}] {summary['content']}\n"
    prompt += f"""

### Instructions
- Organize the summary chronologically. Use time indicators like "On Monday…", "Later that week…", etc.
- Emphasize key actions and decisions.
- Maintain a coherent narrative flow.
- Use dense paragraphs. Do not use formatting.
- Your response cannot exceed {weekly_max_tokens} tokens.
"""
    from shared.models.openai import OpenAICompletionRequest
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
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"http://ledger:{ledger_port}/summary", json=summary_obj.model_dump())
            response.raise_for_status()
        results.append(response.json())
    except Exception as e:
        logger.error(f"Failed to write weekly summary to ledger: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write weekly summary: {e}"
        )
    return results

async def create_monthly_summary(request: SummaryCreateRequest) -> List[dict]:
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
    ledger_port = os.getenv("LEDGER_PORT", 4203)
    api_port = os.getenv("API_PORT", 4200)
    user_id = _config.get("user_id")
    timestamp_begin = request_date.replace(day=1).strftime("%Y-%m-%d 00:00:00")
    last_day = monthrange(request_date.year, request_date.month)[1]
    timestamp_end = request_date.replace(day=last_day).strftime("%Y-%m-%d 23:59:59")
    url = f"http://ledger:{ledger_port}/summary?type=daily"
    url += f"&timestamp_begin={timestamp_begin}&timestamp_end={timestamp_end}"
    try:
        summaries = []
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            summaries.extend(response.json())
    except httpx.HTTPStatusError as e:
        if e.response.status_code == status.HTTP_404_NOT_FOUND:
            logger.info(f"No daily summaries found for {request.date}, skipping.")
            return []
        else:
            logger.error(f"HTTP error from ledger: {e.response.status_code} - {e.response.text}")
            raise
    except Exception as e:
        logger.error(f"Failed to contact ledger to get a list of summaries: {e}")
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
    from shared.models.openai import OpenAICompletionRequest
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
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"http://ledger:{ledger_port}/summary", json=summary_obj.model_dump())
            response.raise_for_status()
        results.append(response.json())
    except Exception as e:
        logger.error(f"Failed to write monthly summary to ledger: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write monthly summary: {e}"
        )
    return results

