"""
Utility functions for topic management in the ledger service.

Functions:
    - topic_exists(topic_id: str) -> bool:
        Checks if a topic with the specified ID exists in the database.

    - _validate_timestamp(ts: str) -> str:
        Validates and normalizes a timestamp string to millisecond precision.
        Accepts formats 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD HH:MM:SS.sss'.
        Raises HTTPException with status 400 if the format is invalid.
"""
from app.util import _open_conn
from fastapi import HTTPException, status
from datetime import datetime
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

def topic_exists(topic_id: str) -> bool:
    """
    Check if a topic with the given ID exists in the database.

    Args:
        topic_id (str): The unique identifier of the topic to check.

    Returns:
        bool: True if the topic exists, False otherwise.
    """
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM topics WHERE id = ?", (topic_id,))
        return cur.fetchone() is not None


def _validate_timestamp(ts: str) -> str:
    """
    Validates and normalizes a timestamp string.

    Accepts timestamp strings in the formats 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD HH:MM:SS.sss'.
    Returns the timestamp as a string with millisecond precision ('YYYY-MM-DD HH:MM:SS.sss').
    Raises an HTTPException with status 400 if the input does not match the expected formats.

    Args:
        ts (str): The timestamp string to validate.

    Returns:
        str: The normalized timestamp string with millisecond precision.

    Raises:
        HTTPException: If the input timestamp format is invalid.
    """
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(ts, fmt)
            # Always return with millisecond precision
            return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        except ValueError:
            continue
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid timestamp format: {ts}. Use 'YYYY-MM-DD HH:MM:SS[.sss]'.")
