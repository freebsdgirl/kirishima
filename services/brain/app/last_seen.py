"""
This module provides utility functions for tracking and managing the "last seen" timestamps of users in the application.
It allows updating, retrieving, and checking the activity status of users based on their last interaction time, using a SQLite database.
Functions:
    - update_last_seen(user_id: str) -> None:
        Updates the last seen timestamp for a specific user in the status database.
    - get_last_seen(user_id: str) -> str:
        Retrieves the last seen timestamp for a specific user from the status database.
    - is_active(user_id: str, threshold: int = 5) -> bool:
        Checks if a user is considered active based on their last seen timestamp and a configurable inactivity threshold (in minutes).
"""

import app.config

from shared.models.notification import LastSeen

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import sqlite3
from datetime import datetime
from fastapi import HTTPException, status


def update_last_seen(request: LastSeen) -> None:
    try:
        with sqlite3.connect(app.config.STATUS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")  # Enable WAL mode
            cursor.execute(
                "INSERT OR REPLACE INTO last_seen (user_id, platform, timestamp) VALUES (?, ?)",
                (request.user_id, request.platform, request.timestamp)
            )
            conn.commit()
            logger.info(f"✅ Last seen for user {request.user_id} on {request.platform} updated to {request.timestamp}")

    except sqlite3.Error as e:
        logger.error(f"Error updating last seen for user {request.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while updating last seen: {e}"
        )


def get_last_seen(user_id: str) -> LastSeen | None:
    """
    Retrieve the last seen timestamp for a specific user from the status database.
    
    Args:
        user_id (str): The unique identifier of the user whose last seen timestamp is to be retrieved.
    
    Returns:
        LastSeen or None: The last seen timestamp in "YYYY-MM-DD HH:MM:SS" format if found, 
                     or None if no timestamp exists for the user.
    
    Raises:
        HTTPException: If an unexpected database error occurs during retrieval, 
                       with a 500 Internal Server Error status code.
    """
    try:
        with sqlite3.connect(app.config.STATUS_DB) as conn:
            conn.row_factory = sqlite3.Row  # This makes fetchone() return a dict-like Row
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute(
                "SELECT user_id, timestamp, platform FROM last_seen WHERE user_id = ?",
                (user_id,)
            )
            result = cursor.fetchone()
            logger.info(f"✅ Last seen for user {user_id} retrieved successfully")
            return LastSeen(**dict(result)) if result else None

    except sqlite3.Error as e:
        logger.error(f"Error retrieving last seen for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while retrieving last seen: {e}"
        )


def is_active(user_id: str, threshold: int = app.config.LAST_SEEN_THRESHOLD):
    """
    Check if a user is considered active based on their last seen timestamp.
    
    Args:
        user_id (str): The unique identifier of the user.
        threshold (int, optional): Maximum minutes of inactivity before user is considered inactive. Defaults to 5.
    
    Returns:
        str: The platform the user was last seen on if they are active, otherwise None.
    """
    last_seen = get_last_seen(user_id)
    if not last_seen:
        return

    # Convert last seen to datetime and compare with current time
    last_seen_time = datetime.strptime(last_seen.timestamp, "%Y-%m-%d %H:%M:%S")

    if (datetime.now() - last_seen_time).total_seconds() / 60 < threshold:
        return last_seen.platform
    else:
        return
