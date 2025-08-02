"""
Calendar notification caching and management.

This module provides functions for caching calendar notifications locally
to avoid sending them to the brain service directly. Notifications can be
retrieved and deleted when needed.
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from app.services.gmail.util import get_config
import sqlite3
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path


def get_db_path() -> str:
    """
    Get the database path from configuration.
    
    Returns:
        str: The path to the calendar database (shared with events cache)
    """
    config = get_config()
    return config.get('db', {}).get('googleapi_calendar', './shared/db/googleapi/calendar.db')


def get_db_connection() -> sqlite3.Connection:
    """
    Get a database connection with proper configuration.
    
    Returns:
        sqlite3.Connection: Database connection with foreign keys enabled
    """
    db_path = get_db_path()
    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_notifications_table():
    """
    Initialize the notifications table in the calendar database.
    
    Creates the notifications table alongside the existing events and calendars tables.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Create notifications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_type TEXT NOT NULL,
                source TEXT NOT NULL,
                data TEXT NOT NULL,  -- JSON storage for notification data
                created_at TEXT NOT NULL,
                read_at TEXT,
                processed BOOLEAN DEFAULT 0
            )
        ''')
        
        # Create indices for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications (notification_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_source ON notifications (source)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications (created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_processed ON notifications (processed)')
        
        conn.commit()
        logger.info("Notifications table initialized successfully in calendar database")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error initializing notifications table: {e}")
        raise
    finally:
        conn.close()


def cache_notification(notification_type: str, source: str, data: Dict[str, Any]) -> int:
    """
    Cache a notification in the database.
    
    Args:
        notification_type: Type of notification (e.g., 'calendar_changes')
        source: Source of the notification (e.g., 'googleapi_calendar_poll')
        data: Notification data to cache
        
    Returns:
        int: The ID of the cached notification
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        created_at = datetime.now(timezone.utc).isoformat()
        
        cursor.execute('''
            INSERT INTO notifications (notification_type, source, data, created_at)
            VALUES (?, ?, ?, ?)
        ''', (notification_type, source, json.dumps(data), created_at))
        
        notification_id = cursor.lastrowid
        conn.commit()
        
        logger.info(f"Cached notification {notification_id}: {notification_type} from {source}")
        return notification_id
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error caching notification: {e}")
        raise
    finally:
        conn.close()


def get_pending_notifications(notification_type: str = None, source: str = None) -> List[Dict[str, Any]]:
    """
    Get pending (unprocessed) notifications.
    
    Args:
        notification_type: Optional filter by notification type
        source: Optional filter by source
        
    Returns:
        List of notification dictionaries
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        query = "SELECT * FROM notifications WHERE processed = 0"
        params = []
        
        if notification_type:
            query += " AND notification_type = ?"
            params.append(notification_type)
            
        if source:
            query += " AND source = ?"
            params.append(source)
            
        query += " ORDER BY created_at ASC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        notifications = []
        for row in rows:
            notification = {
                'id': row['id'],
                'notification_type': row['notification_type'],
                'source': row['source'],
                'data': json.loads(row['data']),
                'created_at': row['created_at'],
                'read_at': row['read_at'],
                'processed': bool(row['processed'])
            }
            notifications.append(notification)
            
        return notifications
        
    except Exception as e:
        logger.error(f"Error getting pending notifications: {e}")
        raise
    finally:
        conn.close()


def mark_notification_processed(notification_id: int):
    """
    Mark a notification as processed.
    
    Args:
        notification_id: ID of the notification to mark as processed
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE notifications 
            SET processed = 1, read_at = ?
            WHERE id = ?
        ''', (datetime.now(timezone.utc).isoformat(), notification_id))
        
        conn.commit()
        logger.info(f"Marked notification {notification_id} as processed")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error marking notification as processed: {e}")
        raise
    finally:
        conn.close()


def delete_processed_notifications(older_than_days: int = 7):
    """
    Delete processed notifications older than specified days.
    
    Args:
        older_than_days: Delete notifications older than this many days
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        cutoff_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).timestamp() - (older_than_days * 24 * 3600)
        
        cursor.execute('''
            DELETE FROM notifications 
            WHERE processed = 1 AND created_at < ?
        ''', (datetime.fromtimestamp(cutoff_date, tz=timezone.utc).isoformat(),))
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} old processed notifications")
            
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting old notifications: {e}")
        raise
    finally:
        conn.close()


def get_notification_stats() -> Dict[str, Any]:
    """
    Get statistics about notifications.
    
    Returns:
        Dict containing notification statistics
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Get total counts
        cursor.execute("SELECT COUNT(*) FROM notifications")
        total_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM notifications WHERE processed = 0")
        pending_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM notifications WHERE processed = 1")
        processed_count = cursor.fetchone()[0]
        
        # Get counts by type
        cursor.execute("""
            SELECT notification_type, COUNT(*) as count 
            FROM notifications 
            GROUP BY notification_type
        """)
        type_counts = {row['notification_type']: row['count'] for row in cursor.fetchall()}
        
        # Get counts by source
        cursor.execute("""
            SELECT source, COUNT(*) as count 
            FROM notifications 
            GROUP BY source
        """)
        source_counts = {row['source']: row['count'] for row in cursor.fetchall()}
        
        return {
            'total_notifications': total_count,
            'pending_notifications': pending_count,
            'processed_notifications': processed_count,
            'by_type': type_counts,
            'by_source': source_counts
        }
        
    except Exception as e:
        logger.error(f"Error getting notification stats: {e}")
        raise
    finally:
        conn.close() 