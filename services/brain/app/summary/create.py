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
from shared.models.summary import SummaryCreateRequest, SummaryMetadata, Summary, SummaryRequest, CombinedSummaryRequest

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
    # connect to the ledger service to get a list of user_ids
    try:
        ledger_port = os.getenv("LEDGER_PORT", 4203)
        response = httpx.get(f"http://ledger:{ledger_port}/active", timeout=timeout)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to trigger create_summary() for period {request.period} and date {request.date}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active users: {e}"
        )
    user_ids = response.json()
    logger.debug(f"Active user IDs: {user_ids}")

    # if nothing is returned, there's no one to summarize.
    if not user_ids:
        return []

    summaries_created = []
    
    # for each user_id, get the buffer
    for user_id in user_ids:
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
        try:
            response = httpx.get(f"http://ledger:{ledger_port}/user/{user_id}/messages", params=params, timeout=timeout)
            response.raise_for_status()
            messages = response.json()
        except Exception as e:
            logger.error(f"Failed to get user messages for user {user_id}, period {params['period']}, date {params['date']}: {e}")
            continue

        # if no messages are listed
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

- The summary should capture the main points and tone of the conversation.
- The summary should be no more than {periodic_max_tokens} tokens in length.
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
                    user_id=user_id,
                    summary_type=request.period,
                    timestamp_begin=chunk[0].created_at,
                    timestamp_end=chunk[-1].created_at
                )
                summaries.append(Summary(content=summary_text, metadata=metadata))
            except Exception as e:
                logger.error(f"Failed to summarize chunk for user {user_id}, period {params['period']}, date {params['date']}: {e}")
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
                    user_id=user_id,
                    summary_type=request.period,
                    timestamp_begin=summaries[0].metadata.timestamp_begin,
                    timestamp_end=summaries[-1].metadata.timestamp_end
                )
                final_summary = Summary(content=combined_text, metadata=metadata)
            except Exception as e:
                logger.error(f"Failed to combine summaries for user {user_id}, period {params['period']}, date {params['date']}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to combine summaries: {e}"
                )
        else:
            final_summary = summaries[0]

        logger.debug(f"Final summary for user {user_id}: {final_summary}")

        try:
            chromadb_port = os.getenv("CHROMADB_PORT", 4206)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(f"http://chromadb:{chromadb_port}/summary", json=final_summary.model_dump())
                response.raise_for_status()
            summaries_created.append(response.json())

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred for user {user_id}, period {params['period']}, date {params['date']}: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Error creating summary: {e.response.text}"
            )

        except Exception as e:
            logger.error(f"Failed to create summary for user {user_id}, period {params['period']}, date {params['date']}: {e}")
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
    chromadb_port = os.getenv("CHROMADB_PORT", 4206)

    # Fetch all period summaries for the date
    summaries = []
    for summary_type in ["night", "morning", "afternoon", "evening"]:
        url = f"http://chromadb:{chromadb_port}/summary?type={summary_type}"
        url += f"&timestamp_begin={request.date}%2000:00:00&timestamp_end={request.date}%2023:59:59"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
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

    # Group by user_id
    user_ids = set(s["metadata"]["user_id"] for s in summaries)
    results = []
    for user_id in user_ids:
        user_summaries = [s for s in summaries if s["metadata"]["user_id"] == user_id]
        user_alias = await get_user_alias(user_id)
        # Build prompt for daily summary
        def format_timestamp(ts: str) -> str:
            dt = datetime.fromisoformat(ts.replace("Z", ""))
            return dt.strftime("%A, %B %d")
        prompt = f"""
### Task: Using the provided summaries, generate a single summary that reflects how events unfolded over time.

### Summaries
"""
        for summary in user_summaries:
            date_str = format_timestamp(summary["metadata"]["timestamp_begin"])
            prompt += f"[{summary['metadata']['summary_type'].upper()} – {date_str}] {summary['content']}\n"
        prompt += f"""

### Instructions
- Organize the summary chronologically. Use time indicators like "In the morning", "In the afternoon", "In the evening" when appropriate.
- Emphasize key actions, decisions, emotional shifts, and recurring themes.
- Your response cannot exceed {daily_max_tokens} tokens.
"""
        from shared.models.openai import OpenAICompletionRequest
        summary_req = OpenAICompletionRequest(
            model="gpt-4.1",
            prompt=prompt,
            max_tokens=daily_max_tokens,
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
            logger.error(f"Failed to summarize daily for user {user_id}, date {request.date}: {e}")
            continue
        # Compose metadata
        metadata = SummaryMetadata(
            user_id=user_id,
            summary_type="daily",  # Use string for rollup type
            timestamp_begin=user_summaries[0]["metadata"]["timestamp_begin"],
            timestamp_end=user_summaries[-1]["metadata"]["timestamp_end"]
        )
        summary_obj = Summary(content=summary_text, metadata=metadata)
        # Store in chromadb
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(f"http://chromadb:{chromadb_port}/summary", json=summary_obj.model_dump())
                response.raise_for_status()
            results.append(response.json())
        except Exception as e:
            logger.error(f"Failed to write daily summary to chromadb for user {user_id}: {e}")
            continue
        # Delete original period summaries for this user
        for s in user_summaries:
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.delete(f"http://chromadb:{chromadb_port}/summary/{s['id']}")
                    response.raise_for_status()
            except Exception as e:
                logger.warning(f"Failed to delete period summary {s['id']} for user {user_id}: {e}")
    return results

async def create_weekly_summary(request: SummaryCreateRequest) -> List[dict]:
    # Weekly summary: aggregate daily summaries for each user for a week (Monday-Sunday)
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
        return
    logger.debug(f"Creating weekly summary for date: {request.date}")
    with open('/app/config/config.json') as f:
        _config = json.load(f)
    timeout = _config["timeout"]
    weekly_max_tokens = _config["summary"].get("weekly_max_tokens", 1024)
    chromadb_port = os.getenv("CHROMADB_PORT", 4206)
    proxy_port = os.getenv("PROXY_PORT", 4205)
    timestamp_begin = request_date.strftime("%Y-%m-%d 00:00:00")
    sunday = request_date + timedelta(days=6)
    timestamp_end = sunday.strftime("%Y-%m-%d 23:59:59")
    url = f"http://chromadb:{chromadb_port}/summary?type=daily"
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
            logger.error(f"HTTP error from chromadb: {e.response.status_code} - {e.response.text}")
            raise
    except Exception as e:
        logger.error(f"Failed to contact chromadb to get a list of summaries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve summaries: {e}")
    if not summaries:
        logger.warning("No summaries found for the specified period.")
        return []
    user_ids = set(s["metadata"]["user_id"] for s in summaries)
    results = []
    for user_id in user_ids:
        user_summaries = [s for s in summaries if s["metadata"]["user_id"] == user_id]
        user_alias = await get_user_alias(user_id)
        # Build prompt for weekly summary (mirroring daily)
        def format_timestamp(ts: str) -> str:
            dt = datetime.fromisoformat(ts.replace("Z", ""))
            return dt.strftime("%A, %B %d")
        prompt = f"""
### Task: Using the provided summaries, generate a single summary that reflects how events unfolded over the week.

### Summaries
"""
        for summary in user_summaries:
            date_str = format_timestamp(summary["metadata"]["timestamp_begin"])
            prompt += f"[{summary['metadata']['summary_type'].upper()} – {date_str}] {summary['content']}\n"
        prompt += f"""

### Instructions
- Organize the summary chronologically. Use time indicators like "On Monday…", "Later that week…", etc.
- Emphasize key actions, decisions, emotional shifts, and recurring themes.
- Maintain a coherent narrative flow.
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
                    f"http://api:{os.getenv('API_PORT', 4200)}/v1/completions",
                    json=summary_req.model_dump()
                )
                response.raise_for_status()
            summary_data = response.json()
            summary_text = summary_data['choices'][0]['content']
        except Exception as e:
            logger.error(f"Failed to summarize weekly for user {user_id}, date {request.date}: {e}")
            continue
        metadata = SummaryMetadata(
            user_id=user_id,
            summary_type="weekly",
            timestamp_begin=user_summaries[0]["metadata"]["timestamp_begin"],
            timestamp_end=user_summaries[-1]["metadata"]["timestamp_end"]
        )
        summary_obj = Summary(content=summary_text, metadata=metadata)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(f"http://chromadb:{chromadb_port}/summary", json=summary_obj.model_dump())
                response.raise_for_status()
            results.append(response.json())
        except Exception as e:
            logger.error(f"Failed to write weekly summary to chromadb for user {user_id}: {e}")
            continue
    return results

async def create_monthly_summary(request: SummaryCreateRequest) -> List[dict]:
    # Monthly summary: aggregate daily summaries for each user for a month
    try:
        request_date = datetime.strptime(request.date, "%Y-%m-%d")
    except ValueError:
        logger.error(f"Invalid date specified: {request.date}. Expected 'YYYY-MM-DD' format.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date specified. Expected 'YYYY-MM-DD' format."
        )
    # If the day is the 1st, roll back to the last day of the previous month
    # we do this because this is called without a date provided, and it's called at midnight - so we need to generate
    # the summary for the previous month, not the current month.
    if request_date.day != 1:
        return
    request_date = request_date - timedelta(days=1)
    from calendar import monthrange
    logger.debug(f"Creating monthly summary for date: {request.date}")
    with open('/app/config/config.json') as f:
        _config = json.load(f)
    timeout = _config["timeout"]
    monthly_max_tokens = _config["summary"].get("monthly_max_tokens", 2048)
    chromadb_port = os.getenv("CHROMADB_PORT", 4206)
    proxy_port = os.getenv("PROXY_PORT", 4205)
    timestamp_begin = request_date.replace(day=1).strftime("%Y-%m-%d 00:00:00")
    last_day = monthrange(request_date.year, request_date.month)[1]
    timestamp_end = request_date.replace(day=last_day).strftime("%Y-%m-%d 23:59:59")
    url = f"http://chromadb:{chromadb_port}/summary?type=daily"
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
            logger.error(f"HTTP error from chromadb: {e.response.status_code} - {e.response.text}")
            raise
    except Exception as e:
        logger.error(f"Failed to contact chromadb to get a list of summaries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve summaries: {e}")
    if not summaries:
        logger.warning("No summaries found for the specified period.")
        return []
    user_ids = set(s["metadata"]["user_id"] for s in summaries)
    results = []
    for user_id in user_ids:
        user_summaries = [s for s in summaries if s["metadata"]["user_id"] == user_id]
        user_alias = await get_user_alias(user_id)
        # Build prompt for monthly summary (mirroring daily)
        def format_timestamp(ts: str) -> str:
            dt = datetime.fromisoformat(ts.replace("Z", ""))
            return dt.strftime("%A, %B %d")
        prompt = f"""
### Task: Using the provided summaries, generate a single summary that reflects how events unfolded over the month.

### Summaries
"""
        for summary in user_summaries:
            date_str = format_timestamp(summary["metadata"]["timestamp_begin"])
            prompt += f"[{summary['metadata']['summary_type'].upper()} – {date_str}] {summary['content']}\n"
        prompt += f"""

### Instructions
- Organize the summary chronologically. Use time indicators like "Early in the month…", "Mid-month…", "By the end of the month…", etc.
- Emphasize key actions, decisions, emotional shifts, and recurring themes.
- Maintain a coherent narrative flow.
- Your response cannot exceed {monthly_max_tokens} tokens.
"""
        from shared.models.openai import OpenAICompletionRequest
        summary_req = OpenAICompletionRequest(
            model="gpt-4.1",
            prompt=prompt,
            max_tokens=monthly_max_tokens,
            temperature=0.7,
            n=1,
            provider="openai"
        )
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"http://api:{os.getenv('API_PORT', 4200)}/v1/completions",
                    json=summary_req.model_dump()
                )
                response.raise_for_status()
            summary_data = response.json()
            summary_text = summary_data['choices'][0]['content']
        except Exception as e:
            logger.error(f"Failed to summarize monthly for user {user_id}, date {request.date}: {e}")
            continue
        metadata = SummaryMetadata(
            user_id=user_id,
            summary_type="monthly",
            timestamp_begin=user_summaries[0]["metadata"]["timestamp_begin"],
            timestamp_end=user_summaries[-1]["metadata"]["timestamp_end"]
        )
        summary_obj = Summary(content=summary_text, metadata=metadata)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(f"http://chromadb:{chromadb_port}/summary", json=summary_obj.model_dump())
                response.raise_for_status()
            results.append(response.json())
        except Exception as e:
            logger.error(f"Failed to write monthly summary to chromadb for user {user_id}: {e}")
            continue
    return results

