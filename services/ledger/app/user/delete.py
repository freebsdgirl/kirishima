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

from typing import Optional
from fastapi import APIRouter, Path, Query
from app.util import _open_conn, get_period_range

router = APIRouter()

TABLE = "user_messages"


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
