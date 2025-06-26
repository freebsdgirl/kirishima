"""
This module provides an API endpoint for deleting user messages from the ledger database.

Functions:
    _open_conn(): Opens a SQLite database connection using configuration from a JSON file.
    get_period_range(period: str, date_str: Optional[str] = None): Calculates the start and end datetime for a given period and date.
    delete_user_buffer(user_id: str, period: Optional[str], date: Optional[str]) -> DeleteSummary:
        FastAPI route handler to delete messages for a specific user, optionally filtered by time period and date.

Routes:
    DELETE /user/{user_id}:
        Deletes all messages for a user, or only those in a specified period and date.
        If no period is specified, retains the 10 most recent messages for the user.

Dependencies:
    - shared.models.ledger.DeleteSummary: Response model for deletion summary.
    - shared.log_config.get_logger: Logger configuration.
    - fastapi.APIRouter, Path, Query: FastAPI routing and parameter utilities.
    - sqlite3, json, datetime, typing.Optional

Constants:
    TABLE: Name of the user messages table in the database.
"""

from shared.models.ledger import  DeleteSummary

from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

import sqlite3
import json
from typing import Optional
from fastapi import APIRouter, Path, Query
from datetime import datetime, time, timedelta

router = APIRouter()

TABLE = "user_messages"


def _open_conn() -> sqlite3.Connection:
    """
    Opens a SQLite database connection using the path specified in the configuration file.

    Reads the database path from '/app/config/config.json' under the key ["db"]["ledger"],
    establishes a connection with a 5-second timeout, and sets the journal mode to WAL.

    Returns:
        sqlite3.Connection: An open connection to the specified SQLite database.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)

    db = _config["db"]["ledger"]
    conn = sqlite3.connect(db, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def get_period_range(period: str, date_str: Optional[str] = None):
    """
    Returns the start and end datetime objects for a given period of the day.

    Args:
        period (str): The period of the day. Must be one of "night", "morning", "afternoon", "evening", or "day".
        date_str (Optional[str], optional): The date in "YYYY-MM-DD" format. If not provided, uses the current date,
            or for "evening" and "day" periods, defaults to the previous day.

    Returns:
        Tuple[datetime, datetime]: A tuple containing the start and end datetime objects for the specified period.

    Raises:
        ValueError: If the provided period is not one of the accepted values.
    """
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
