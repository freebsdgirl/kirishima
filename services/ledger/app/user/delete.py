"""
This module provides an API endpoint for deleting user messages from the ledger buffer database.
It allows deletion of all messages for a specific user, or only those within a specified time period and date.

Functions:
    _open_conn(): Opens a SQLite connection to the buffer database with WAL journal mode.
    get_period_range(period: str, date_str: Optional[str] = None): 
        Returns the start and end datetime objects for a given period and optional date.
    delete_user_buffer(user_id: str, period: Optional[str], date: Optional[str]) -> DeleteSummary:
        FastAPI route handler to delete user messages, filtered by period and date if provided.

Routes:
    DELETE /ledger/user/{user_id}:
        Deletes all messages for the specified user, or only those in a given period and date.
        Returns a summary of the number of deleted messages.
"""

from app.config import BUFFER_DB
from shared.models.ledger import  DeleteSummary

from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

import sqlite3
from typing import Optional
from fastapi import APIRouter, Path, Query
from datetime import datetime, time, timedelta

router = APIRouter()

TABLE = "user_messages"


def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(BUFFER_DB, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def get_period_range(period: str, date_str: Optional[str] = None):
    # Determine default date based on period if not provided
    if date_str is None:
        now = datetime.now()
        if period in ("evening", "day"):
            date = (now - timedelta(days=1)).date()
        else:
            date = now.date()
    else:
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


@router.delete("/user/{user_id}", response_model=DeleteSummary)
def delete_user_buffer(
    user_id: str = Path(...),
    period: Optional[str] = Query(None, description="Time period to filter messages (e.g., 'morning', 'afternoon', etc.)"),
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format. Defaults to today."),
) -> DeleteSummary:
    """
    Delete all messages for a specific user, or only those in a given period and date.

    Args:
        user_id (str): The unique identifier of the user whose messages will be deleted.
        period (Optional[str]): Time period to filter messages.
        date (Optional[str]): Date in YYYY-MM-DD format.

    Returns:
        DeleteSummary: An object containing the count of deleted messages.
    """

    logger.debug(f"Deleting messages for user {user_id} (period={period}, date={date})")

    with _open_conn() as conn:
        cur = conn.cursor()
        if period:
            start, end = get_period_range(period, date)
            cur.execute(
                f"DELETE FROM {TABLE} WHERE user_id = ? AND created_at >= ? AND created_at <= ?",
                (user_id, start.strftime("%Y-%m-%d %H:%M:%S.%f"), end.strftime("%Y-%m-%d %H:%M:%S.%f")),
            )
        else:
            cur.execute(
                f"""
                DELETE FROM {TABLE}
                WHERE user_id = ?
                  AND ROWID NOT IN (
                    SELECT ROWID FROM {TABLE}
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 10
                  )
                """,
                (user_id, user_id)
            )
        deleted = cur.rowcount
        conn.commit()
        return DeleteSummary(deleted=deleted)
