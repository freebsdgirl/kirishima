import app.config

from shared.models.notification import NotificationCreateRequest, Notification

from app.last_seen import is_active
from app.notification.util import _send_discord_dm, _send_imessage, _get_contact
from app.notification.delete import notification_delete

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import sqlite3

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/notification/execute")
async def notification_execute():
    """
    Execute pending notifications for users across different platforms.

    This endpoint retrieves all notifications from the database and attempts to send them
    via iMessage or Discord based on the user's activity status and available contact methods.
    For active web users, no notification is sent. For inactive or non-web users, the system
    tries to send notifications through iMessage first, then falls back to Discord.

    Notifications are deleted after successful delivery.

    Raises:
        HTTPException: If there are issues retrieving contacts or sending notifications.
    """
    try:
        with sqlite3.connect(app.config.STATUS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute(
                "SELECT id, user_id, notification, timestamp, status FROM notifications"
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

    except sqlite3.Error as e:
        logger.error(f"Error retrieving notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while retrieving notifications: {e}"
        )

    # step through each notification
    for notification in notifications:
        platform = is_active(notification.user_id)

        if platform:
            if platform == "web":
                logger.debug(f"User {notification.user_id} is active on web. No action needed.")
                continue

            # Fetch contact info for non-web platforms
            try:
                contact = await _get_contact(notification.user_id)
            except HTTPException as e:
                logger.error(f"Failed to retrieve contact for {notification.user_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to retrieve contact: {e}"
                )

            if not contact:
                logger.debug(f"No contact found for {notification.user_id}, skipping.")
                continue

            # Send via iMessage if available
            if contact.get("imessage"):
                try:
                    await _send_imessage(contact["imessage"], notification.notification)
                    logger.info(f"✅ Notification sent to {notification.user_id} via iMessage")
                except Exception as e:
                    logger.error(f"Failed to send iMessage: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to send notification via iMessage: {e}"
                    )
                notification_delete(notification.id)

            # Otherwise, send via Discord if available
            elif contact.get("discord_id"):
                try:
                    await _send_discord_dm(contact["discord_id"], notification.notification)
                    logger.info(f"✅ Notification sent to {notification.user_id} via Discord")
                except Exception as e:
                    logger.error(f"Failed to send Discord DM: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to send notification via Discord: {e}"
                    )
                notification_delete(notification.id)

        else:
            logger.debug(f"User {notification.user_id} is not active. Sending notification {notification.id}.")
            try:
                contact = await _get_contact(notification.user_id)
            except HTTPException as e:
                logger.error(f"Failed to retrieve contact for {notification.user_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to retrieve contact: {e}"
                )

            if not contact:
                logger.debug(f"No contact found for {notification.user_id}, skipping.")
                continue

            # Send via iMessage if available
            if contact.get("imessage"):
                try:
                    await _send_imessage(contact["imessage"], notification.notification)
                    logger.info(f"✅ Notification sent to {notification.user_id} via iMessage")
                except Exception as e:
                    logger.error(f"Failed to send iMessage: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to send notification via iMessage: {e}"
                    )
                notification_delete(notification.id)

            # Otherwise, send via Discord if available
            elif contact.get("discord_id"):
                try:
                    await _send_discord_dm(contact["discord_id"], notification.notification)
                    logger.info(f"✅ Notification sent to {notification.user_id} via Discord")
                except Exception as e:
                    logger.error(f"Failed to send Discord DM: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to send notification via Discord: {e}"
                    )
                notification_delete(notification.id)

            else:
                logger.debug(f"No iMessage or Discord contact found for {notification.user_id}, skipping.")
                continue
