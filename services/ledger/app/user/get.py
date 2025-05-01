"""
This module provides API endpoints and utility functions for retrieving user messages
from the ledger service. It includes:
- A utility function `get_period_range` to compute datetime ranges for named periods
    (e.g., 'morning', 'afternoon', etc.) on a given date.
- An endpoint `/ledger/user/{user_id}/messages` to fetch messages for a specific user,
    with optional filtering by time period and date.
- An endpoint `/active` to retrieve all unique user IDs with messages in the database.
The module uses FastAPI for routing, SQLite for data storage, and shared models and
logging configuration for consistent data handling and logging.
"""

from app.config import BUFFER_DB
from shared.models.ledger import CanonicalUserMessage

from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

import sqlite3
from typing import List, Optional
from datetime import datetime, time, timedelta
from fastapi import APIRouter, Path, Body, Query

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
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format. Defaults to today unless time is 00:00, then yesterday.")
) -> List[CanonicalUserMessage]:
    """
    Retrieve messages for a specific user, optionally filtered by time period.

    Args:
        user_id (str): The unique identifier of the user.
        period (Optional[str], optional): Time period to filter messages (e.g., 'morning', 'afternoon'). Defaults to None.
        date (Optional[str], optional): Date in YYYY-MM-DD format to filter messages. Defaults to today or yesterday.

    Returns:
        List[CanonicalUserMessage]: A list of messages for the specified user, optionally filtered by time period.

    Raises:
        ValueError: If an invalid period is specified.
    """
    logger.debug(f"Fetching messages for user {user_id} (date={date}, period={period})")

    # Default date logic
    if period and not date:
        now = datetime.now()
        if now.hour == 0 and now.minute == 0:
            date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            date = now.strftime("%Y-%m-%d")

    with sqlite3.connect(BUFFER_DB, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_messages WHERE user_id = ? ORDER BY id", (user_id,))
        columns = [col[0] for col in cur.description]
        messages = [CanonicalUserMessage(**dict(zip(columns, row))) for row in cur.fetchall()]
        if period:
            start, end = get_period_range(period, date)
            def parse_created_at(dt_str):
                # Handles "YYYY-MM-DD HH:MM:SS.sss"
                return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S.%f")
            messages = [
                msg for msg in messages
                if start <= parse_created_at(msg.created_at) <= end
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
    with sqlite3.connect(BUFFER_DB, timeout=5.0, isolation_level=None) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT user_id FROM user_messages"
        )
        user_ids = [row[0] for row in cur.fetchall()]
        logger.debug(f"Found {len(user_ids)} unique user IDs in the database.")
        return user_ids
