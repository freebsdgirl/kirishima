"""
Notification endpoints for the googleapi service.

This module provides endpoints for retrieving and managing cached notifications
from various sources (calendar, gmail, etc.).
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from shared.log_config import get_logger
from app.services.calendar.notifications import (
    init_notifications_table,
    get_pending_notifications,
    mark_notification_processed,
    get_notification_stats,
    delete_processed_notifications
)

logger = get_logger(f"googleapi.{__name__}")

router = APIRouter()


@router.get("/notifications", response_model=Dict[str, Any])
async def get_notifications_endpoint(
    notification_type: Optional[str] = None,
    source: Optional[str] = None,
    mark_processed: bool = True
):
    """
    Get pending notifications.
    
    Args:
        notification_type: Optional filter by notification type
        source: Optional filter by source
        mark_processed: Whether to mark notifications as processed after retrieval
        
    Returns:
        Dict containing notifications and metadata
    """
    try:
        # Initialize notifications table if needed
        init_notifications_table()
        
        # Get pending notifications
        notifications = get_pending_notifications(
            notification_type=notification_type,
            source=source
        )
        
        # Mark as processed if requested
        if mark_processed and notifications:
            for notification in notifications:
                mark_notification_processed(notification['id'])
        
        return {
            'success': True,
            'notifications': notifications,
            'count': len(notifications),
            'filters': {
                'notification_type': notification_type,
                'source': source,
                'mark_processed': mark_processed
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get notifications: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notifications/stats", response_model=Dict[str, Any])
async def get_notification_stats_endpoint():
    """
    Get notification statistics.
    
    Returns:
        Dict containing notification statistics
    """
    try:
        # Initialize notifications table if needed
        init_notifications_table()
        
        stats = get_notification_stats()
        
        return {
            'success': True,
            'stats': stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get notification stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notifications/{notification_id}/process")
async def mark_notification_processed_endpoint(notification_id: int):
    """
    Mark a specific notification as processed.
    
    Args:
        notification_id: ID of the notification to mark as processed
        
    Returns:
        Dict containing processing status
    """
    try:
        mark_notification_processed(notification_id)
        
        return {
            'success': True,
            'message': f'Notification {notification_id} marked as processed'
        }
        
    except Exception as e:
        logger.error(f"Failed to mark notification {notification_id} as processed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/notifications/cleanup")
async def cleanup_old_notifications_endpoint(older_than_days: int = 7):
    """
    Delete processed notifications older than specified days.
    
    Args:
        older_than_days: Delete notifications older than this many days
        
    Returns:
        Dict containing cleanup status
    """
    try:
        delete_processed_notifications(older_than_days)
        
        return {
            'success': True,
            'message': f'Cleaned up notifications older than {older_than_days} days'
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup old notifications: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 