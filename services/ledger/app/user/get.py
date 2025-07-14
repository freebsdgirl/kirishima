"""
This module provides FastAPI endpoints for retrieving and filtering user messages
from the ledger database. It includes utilities for time period filtering, 
fetching all messages, untagged messages, and the timestamp of the last message 
for a user. The endpoints support filtering by period, date, and explicit 
timestamp ranges, and ensure that tool messages and empty assistant messages 
are excluded from results.
Endpoints:
- /user/{user_id}/messages: Retrieve messages for a user, with optional time filtering.
- /active: List all unique user IDs with messages in the database.
- /user/{user_id}/messages/untagged: Retrieve untagged messages for a user.
- /user/{user_id}/messages/last: Get the timestamp of the user's most recent message.
Utility Functions:
- get_period_range: Convert a period string and optional date into a datetime range.
"""

from shared.models.ledger import CanonicalUserMessage
from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

import sqlite3
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Path, Query
import json
from app.util import get_period_range

router = APIRouter()


@router.get("/user/{user_id}/messages", response_model=List[CanonicalUserMessage])
def get_user_messages(
    user_id: str = Path(...),
    period: Optional[str] = Query(None, description="Time period to filter messages (e.g., 'morning', 'afternoon', etc.)"),
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format. Defaults to today unless time is 00:00, then yesterday."),
    start: Optional[str] = Query(None, description="Start timestamp (ISO 8601, e.g. '2025-06-29T00:00:00'). If provided, overrides period/date filtering."),
    end: Optional[str] = Query(None, description="End timestamp (ISO 8601, e.g. '2025-06-29T23:59:59'). If provided, overrides period/date filtering.")
) -> List[CanonicalUserMessage]:
    """
    Retrieve messages for a specific user, optionally filtered by time period, date, or explicit start/end timestamps.

    Args:
        user_id (str): The unique identifier of the user.
        period (Optional[str], optional): Time period to filter messages (e.g., 'morning', 'afternoon'). Defaults to None.
        date (Optional[str], optional): Date in YYYY-MM-DD format to filter messages. Defaults to today or yesterday.
        start (Optional[str], optional): Start timestamp (ISO 8601). If provided, overrides period/date filtering.
        end (Optional[str], optional): End timestamp (ISO 8601). If provided, overrides period/date filtering.

    Returns:
        List[CanonicalUserMessage]: A list of messages for the specified user, filtered as requested.

    Raises:
        ValueError: If an invalid period is specified.
    """
    logger.debug(f"Fetching messages for user {user_id} (date={date}, period={period}, start={start}, end={end})")

    # Default date logic
    if period and not date:
        now = datetime.now()
        if now.hour == 0 and now.minute == 0:
            date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            date = now.strftime("%Y-%m-%d")

    with open('/app/config/config.json') as f:
        _config = json.load(f)

    db = _config["db"]["ledger"]

    with sqlite3.connect(db, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_messages WHERE user_id = ? ORDER BY id", (user_id,))
        columns = [col[0] for col in cur.description]
        raw_messages = [dict(zip(columns, row)) for row in cur.fetchall()]
        for msg in raw_messages:
            if msg.get("tool_calls"):
                try:
                    msg["tool_calls"] = json.loads(msg["tool_calls"])
                except Exception:
                    msg["tool_calls"] = None
            if msg.get("function_call"):
                try:
                    msg["function_call"] = json.loads(msg["function_call"])
                except Exception:
                    msg["function_call"] = None
        messages = [CanonicalUserMessage(**msg) for msg in raw_messages]
        # Filter out tool messages and assistant messages with empty content
        messages = [
            msg for msg in messages
            if not (
                getattr(msg, 'role', None) == 'tool' or
                (getattr(msg, 'role', None) == 'assistant' and not getattr(msg, 'content', None))
            )
        ]
        # Remove tool/function call fields from returned messages
        for msg in messages:
            if hasattr(msg, 'tool_calls'):
                msg.tool_calls = None
            if hasattr(msg, 'function_call'):
                msg.function_call = None
        # New: filter by start/end if provided
        if start and end:
            try:
                # Accept 'YYYY-MM-DD HH:MM:SS.sss' (to milliseconds)
                start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S.%f")
                end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M:%S.%f")
            except Exception:
                raise ValueError("Invalid start or end timestamp format. Use 'YYYY-MM-DD HH:MM:SS.sss'.")
            def parse_created_at(dt_str):
                return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S.%f")
            messages = [
                msg for msg in messages
                if start_dt <= parse_created_at(msg.created_at) <= end_dt
            ]
        elif period:
            start_dt, end_dt = get_period_range(period, date)
            def parse_created_at(dt_str):
                return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S.%f")
            messages = [
                msg for msg in messages
                if start_dt <= parse_created_at(msg.created_at) <= end_dt
            ]
        return messages


@router.get("/active")
async def trigger_summaries_for_inactive_users():
    """
    Retrieve a list of unique user IDs from the user messages database.

    This endpoint returns all distinct user IDs that have messages in the database.
    Useful for identifying active or potentially inactive users across the system.

    Returns:
        List[str]: A list of unique user IDs found in the user messages database.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)

    db = _config["db"]["ledger"]

    with sqlite3.connect(db, timeout=5.0, isolation_level=None) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT user_id FROM user_messages"
        )
        user_ids = [row[0] for row in cur.fetchall()]
        logger.debug(f"Found {len(user_ids)} unique user IDs in the database.")
        return user_ids


@router.get("/user/{user_id}/messages/untagged", response_model=List[CanonicalUserMessage])
def get_user_untagged_messages(user_id: str = Path(...)) -> List[CanonicalUserMessage]:
    """
    Retrieve all untagged messages for a given user from the database.

    This function fetches messages from the `user_messages` table where the `user_id` matches
    the provided value and `topic_id` is NULL (untagged). The messages are ordered by their `id`.
    It filters out messages where the role is 'tool' or where the role is 'assistant' and the content is empty.

    Args:
        user_id (str): The ID of the user whose untagged messages are to be retrieved.

    Returns:
        List[CanonicalUserMessage]: A list of CanonicalUserMessage objects representing the user's untagged messages,
        excluding tool messages and assistant messages with empty content.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)
    db = _config["db"]["ledger"]
    with sqlite3.connect(db, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_messages WHERE user_id = ? AND topic_id IS NULL ORDER BY id", (user_id,))
        columns = [col[0] for col in cur.description]
        raw_messages = [dict(zip(columns, row)) for row in cur.fetchall()]
        for msg in raw_messages:
            if msg.get("tool_calls"):
                try:
                    msg["tool_calls"] = json.loads(msg["tool_calls"])
                except Exception:
                    msg["tool_calls"] = None
            if msg.get("function_call"):
                try:
                    msg["function_call"] = json.loads(msg["function_call"])
                except Exception:
                    msg["function_call"] = None
        messages = [CanonicalUserMessage(**msg) for msg in raw_messages]
        # Filter out tool messages and assistant messages with empty content
        messages = [
            msg for msg in messages
            if not (
                getattr(msg, 'role', None) == 'tool' or
                (getattr(msg, 'role', None) == 'assistant' and not getattr(msg, 'content', None))
            )
        ]
        return messages


@router.get("/user/{user_id}/messages/last", response_model=str)
def get_last_message_timestamp(user_id: str = Path(...)) -> str:
    """
    Retrieves the timestamp of the most recent message sent by a specific user.

    Args:
        user_id (str): The unique identifier of the user.

    Returns:
        str: The timestamp of the latest message sent by the user in the 'created_at' field,
             or an empty string if no messages are found.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)
    db = _config["db"]["ledger"]
    with sqlite3.connect(db, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute("SELECT created_at FROM user_messages WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))
        row = cur.fetchone()
        return row[0] if row else ""
