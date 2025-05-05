"""
This module provides an API endpoint for retrieving notifications for a specific user
from the status database.

Endpoints:
    - GET /notification/{user_id}: Retrieve a list of notifications for the specified user.

Modules:
    - app.config: Application configuration, including database paths.
    - shared.models.notification: Notification data model.
    - shared.log_config: Logger configuration.
    - sqlite3: SQLite database access.
    - fastapi: FastAPI framework for API routing and exception handling.

Functions:
    - notification_get(user_id: str) -> list[Notification]:
        Retrieves notifications for a given user from the database and returns them as a list
        of Notification objects. Handles database errors and logs relevant information.
"""
import app.config

from shared.models.notification import Notification

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import sqlite3

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.get("/notification/{user_id}", response_model=list[Notification])
def notification_get(user_id: str) -> list:
    """
    Retrieve notifications for a specific user from the status database.

    Args:
        user_id (str): The unique identifier of the user whose notifications are to be retrieved.

    Returns:
        list[Notification]: A list of notification objects for the specified user.

    Raises:
        HTTPException: If an unexpected error occurs during database retrieval, 
        with a 500 Internal Server Error status code.
    """
    logger.debug(f"Retrieving notifications for user {user_id}")

    try:
        with sqlite3.connect(app.config.STATUS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute(
                "SELECT id, user_id, notification, timestamp, status FROM notifications WHERE user_id = ?",
                (user_id,)
            )
            rows = cursor.fetchall()

            notifications = []
            for row in rows:
                notifications.append(
                    Notification(
                        id=row[0],
                        user_id=row[1],
                        notification=row[2],
                        timestamp=row[3],
                        status=row[4]
                    )
                )

            logger.info(f"✅ Retrieved {len(notifications)} notifications for user {user_id}")

    except sqlite3.Error as e:
        logger.error(f"Error retrieving notifications for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while retrieving notifications: {e}"
        )

    return notifications
