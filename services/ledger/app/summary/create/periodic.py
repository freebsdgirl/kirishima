"""
This module provides functionality to asynchronously create periodic summaries of user-assistant conversations for specified periods and dates.

Functions:
    create_periodic_summary(request: SummaryCreateRequest) -> List[dict]:
        Asynchronously generates a summary of conversations for a given user, period, and date. The function retrieves messages, chunks them to fit within token limits, summarizes each chunk using an external language model API, and combines summaries if necessary. The final summary is then inserted into the database.

Constants:
    VALID_PERIODS: List of valid period strings for which summaries can be created.
    ALL_PERIODS: List of all possible period strings, including aggregate periods.

    The module uses structured logging to trace the summary creation process, including debug, warning, and error messages.
"""
from shared.models.ledger import SummaryCreateRequest, SummaryMetadata, Summary

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from datetime import datetime, timedelta
from fastapi import HTTPException, status
from app.user.get import _get_user_messages
from app.summary.post import _insert_summary
from typing import List
import httpx
import json
import os
from transformers import AutoTokenizer
from shared.models.ledger import CanonicalUserMessage
from shared.models.openai import OpenAICompletionRequest


VALID_PERIODS = ["night", "morning", "afternoon", "evening"]
ALL_PERIODS = VALID_PERIODS + ["daily", "weekly", "monthly"]

async def create_periodic_summary(request: SummaryCreateRequest) -> List[dict]:
    """
    Asynchronously creates a periodic summary of user-assistant conversations for a specified period and date.

    This function retrieves user messages for the given period and date, chunks them to fit within token limits,
    and generates concise summaries using an external language model API. If multiple chunks are summarized,
    their summaries are combined into a single summary. The final summary is then inserted into the database.

    Args:
        request (SummaryCreateRequest): The request object containing the period and date for which to create the summary.

    Returns:
        List[dict]: A list containing the created summary as a dictionary.

    Raises:
        HTTPException: If the period is invalid, if summaries cannot be generated or combined, or if insertion fails.

    Logging:
        Logs debug, warning, and error messages throughout the process for traceability.
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


    # Use internal helper to get messages for the user
    try:
        messages = _get_user_messages(user_id=user_id, period=params["period"], date=params["date"])
    except Exception as e:
        logger.error(f"Failed to get user messages for user {user_id}, period {params['period']}, date {params['date']}: {e}")
        return []

    if not messages:
        logger.warning(f"No messages found for user {user_id} for period {request.period} on date {request.date}")
        return []

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
        user_label = "Randi"
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
        result = _insert_summary(final_summary)
        summaries_created.append(result.model_dump())
    except Exception as e:
        logger.error(f"Failed to create summary for period {params['period']}, date {params['date']}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create summary: {e}"
        )
    return summaries_created