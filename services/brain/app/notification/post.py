"""
This module provides an API endpoint for creating and storing notifications for users.
It defines a FastAPI router with a POST endpoint that accepts notification creation requests,
constructs Notification objects, and persists them in a SQLite database. The module includes
error handling for database operations and logs relevant events for monitoring and debugging.
Dependencies:
    - FastAPI for API routing and HTTP exception handling
    - SQLite3 for database interactions
    - Shared models for request and notification data structures
    - Shared logging configuration for consistent logging
Endpoints:
    - POST /notification: Accepts a NotificationCreateRequest and stores the notification in the database.
"""
import app.config

from shared.models.notification import NotificationCreateRequest, Notification

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import sqlite3

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/notification", status_code=status.HTTP_200_OK, response_model=dict)
def notification_post(request: NotificationCreateRequest) -> dict:
    """
    Create and store a notification for a specific user.

    This endpoint receives a notification request, creates a Notification object,
    and stores it in the SQLite database. It handles potential database errors
    and returns a success message upon successful storage.

    Args:
        request (NotificationCreateRequest): Contains user_id and notification details

    Returns:
        dict: A message confirming successful notification storage

    Raises:
        HTTPException: If there is an error storing the notification in the database
    """
    logger.debug(f"Storing notification for user {request.user_id}: {request.notification}")

    notification = Notification(
        user_id=request.user_id,
        notification=request.notification
    )

    try:
        with sqlite3.connect(app.config.STATUS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute(
                "INSERT INTO notifications (id, user_id, notification, timestamp, status) VALUES (?, ?, ?, ?, ?)",
                (notification.id, notification.user_id, notification.notification, notification.timestamp, notification.status)
            )
            conn.commit()
            logger.info(f"✅ Notification stored for user {notification.user_id}")

    except sqlite3.Error as e:
        logger.error(f"Error storing notification for user {notification.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while storing notification: {e}"
        )
    
    return {'message': 'Notification stored successfully'}
