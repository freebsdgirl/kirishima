"""
This module provides functionality to delete a specific notification from the status database.
Functions:
    notification_delete(notification_id: str) -> dict:
        Deletes a notification by its unique identifier from the notifications table in the status database.
        Logs the deletion process and handles database errors by raising an HTTPException with a 500 status code.
"""
from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import sqlite3
import json

from fastapi import HTTPException, status


def notification_delete(notification_id: str) -> dict:
    """
    Delete a specific notification by its ID from the status database.
    
    Args:
        notification_id (str): The unique identifier of the notification to delete.
    
    Returns:
        dict: A confirmation message indicating successful deletion.
    
    Raises:
        HTTPException: If an unexpected error occurs during database deletion, 
        with a 500 Internal Server Error status code.
    """
    logger.debug(f"Deleting notification {notification_id}")


    with open('/app/config/config.json') as f:
        _config = json.load(f)

    db = _config["db"]["status"]
    if not db:
        logger.error("Database path is not configured.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database path is not configured."
        )

    try:
        with sqlite3.connect(db) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute(
                "DELETE FROM notifications WHERE id = ?",
                (notification_id,)
            )
            conn.commit()
            logger.info(f"✅ Notification {notification_id} deleted.")

    except sqlite3.Error as e:
        logger.error(f"Error deleting notification {notification_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while deleting notification: {e}"
        )

    return {'message': 'Notification deleted successfully'}
