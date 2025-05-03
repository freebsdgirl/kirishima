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

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import sqlite3
from datetime import datetime
from fastapi import HTTPException, status


def update_last_seen(user_id: str) -> None:
    """
    Update the last seen timestamp for a specific user in the status database.
    
    Args:
        user_id (str): The unique identifier of the user whose last seen timestamp is to be updated.
    
    Raises:
        HTTPException: If an unexpected database error occurs during update, 
                       with a 500 Internal Server Error status code.
    """
    last_seen = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with sqlite3.connect(app.config.STATUS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")  # Enable WAL mode
            cursor.execute(
                "INSERT OR REPLACE INTO status (key, value) VALUES (?, ?)",
                (f"last_seen_{user_id}", last_seen)
            )
            conn.commit()
            logger.info(f"✅ Last seen for user {user_id} updated to {last_seen}")

    except sqlite3.Error as e:
        logger.error(f"Error updating last seen for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while updating last seen: {e}"
        )


def get_last_seen(user_id: str) -> str:
    """
    Retrieve the last seen timestamp for a specific user from the status database.
    
    Args:
        user_id (str): The unique identifier of the user whose last seen timestamp is to be retrieved.
    
    Returns:
        str or None: The last seen timestamp in "YYYY-MM-DD HH:MM:SS" format if found, 
                     or None if no timestamp exists for the user.
    
    Raises:
        HTTPException: If an unexpected database error occurs during retrieval, 
                       with a 500 Internal Server Error status code.
    """
    try:
        with sqlite3.connect(app.config.STATUS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")  # En
            cursor.execute(
                "SELECT value FROM status WHERE key = ?",
                (f"last_seen_{user_id}",)
            )
            result = cursor.fetchone()
            logger.info(f"✅ Last seen for user {user_id} retrieved successfully")
            return result[0] if result else None

    except sqlite3.Error as e:
        logger.error(f"Error retrieving last seen for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while retrieving last seen: {e}"
        )


def is_active(user_id: str, threshold: int = 5) -> bool:
    """
    Check if a user is considered active based on their last seen timestamp.
    
    Args:
        user_id (str): The unique identifier of the user.
        threshold (int, optional): Maximum minutes of inactivity before user is considered inactive. Defaults to 5.
    
    Returns:
        bool: True if the user has been active within the threshold, False otherwise.
    """
    last_seen = get_last_seen(user_id)
    if not last_seen:
        return False

    # Convert last seen to datetime and compare with current time
    last_seen_time = datetime.strptime(last_seen, "%Y-%m-%d %H:%M:%S")
    return (datetime.now() - last_seen_time).total_seconds() / 60 < threshold
