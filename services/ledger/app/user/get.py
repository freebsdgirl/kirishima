"""
This module provides API endpoints for retrieving user messages from the ledger service.
Endpoints:
- GET /user/{user_id}/messages: Retrieve messages for a specific user, optionally filtered by time period and date.
- GET /active: Retrieve a list of unique user IDs that have messages in the database.
Functions:
- get_period_range(period: str, date_str: Optional[str] = None): 
    Converts a period string and optional date into a start and end datetime range.
- get_user_messages(
    user_id: str,
    period: Optional[str] = None,
    date: Optional[str] = None
    Retrieves messages for a specific user, with optional filtering by time period and date.
- trigger_summaries_for_inactive_users():
    Retrieves a list of unique user IDs from the user messages database.
Dependencies:
- FastAPI for API routing.
- sqlite3 for database access.
- CanonicalUserMessage model for message serialization.
- Shared logging configuration.
- JSON for configuration and message parsing.
Note:
- Time period filtering supports 'night', 'morning', 'afternoon', 'evening', and 'day'.
- Tool messages and assistant messages with empty content are filtered out from results.

"""

from shared.models.ledger import CanonicalUserMessage

from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

import sqlite3
from typing import List, Optional
from datetime import datetime, time, timedelta
from fastapi import APIRouter, Path, Query
import json

router = APIRouter()

def get_period_range(period: str, date_str: Optional[str] = None):
    """
    Convert a period string and optional date into a start and end datetime range.
    
    Args:
        period (str): The time period to generate a range for. 
            Valid periods are: 'night', 'morning', 'afternoon', 'evening', 'day'.
        date_str (Optional[str], optional): Date in YYYY-MM-DD format. 
            Defaults to the current date if not provided.
    
    Returns:
        Tuple[datetime, datetime]: A tuple containing the start and end datetime for the specified period.
    
    Raises:
        ValueError: If an invalid period is provided.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    date = datetime.strptime(date_str, "%Y-%m-%d").date()
    if period == "night":
        start = datetime.combine(date, time(0, 0))
        end = datetime.combine(date, time(5, 59, 59, 999999))
    elif period == "morning":
        start = datetime.combine(date, time(6, 0))
        end = datetime.combine(date, time(11, 59, 59, 999999))
    elif period == "afternoon":
        start = datetime.combine(date, time(12, 0))
        end = datetime.combine(date, time(17, 59, 59, 999999))
    elif period == "evening":
        start = datetime.combine(date, time(18, 0))
        end = datetime.combine(date, time(23, 59, 59, 999999))
    elif period == "day":
        start = datetime.combine(date, time(0, 0))
        end = datetime.combine(date, time(23, 59, 59, 999999))
    else:
        raise ValueError("Invalid period")
    return start, end


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
    Retrieve all messages for a user that do not have a topic_id assigned (topic_id IS NULL).
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
