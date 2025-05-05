"""
This module provides functionality to delete a specific notification from the status database.
Functions:
    notification_delete(notification_id: str) -> dict:
        Deletes a notification by its unique identifier from the notifications table in the status database.
        Logs the deletion process and handles database errors by raising an HTTPException with a 500 status code.
"""
import app.config

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import sqlite3

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

    try:
        with sqlite3.connect(app.config.STATUS_DB) as conn:
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
