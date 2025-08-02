"""
Calendar event caching utilities.

This module provides functions for caching calendar events locally
and detecting changes between polling cycles.
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from app.services.gmail.util import get_config
import sqlite3
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path


def get_db_path() -> str:
    """Get the database path from configuration."""
    config = get_config()
    return config.get('db', {}).get('googleapi_calendar', './shared/db/googleapi/calendar.db')


def get_db_connection() -> sqlite3.Connection:
    """Get a database connection with proper configuration."""
    db_path = get_db_path()
    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_cache_db():
    """Initialize the event cache database."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Create events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                calendar_id TEXT NOT NULL,
                summary TEXT,
                description TEXT,
                location TEXT,
                start_datetime TEXT,
                end_datetime TEXT,
                start_date TEXT,
                end_date TEXT,
                created TEXT,
                updated TEXT,
                status TEXT,
                transparency TEXT,
                visibility TEXT,
                event_data TEXT NOT NULL,  -- JSON storage for full event data
                cached_at TEXT NOT NULL
            )
        ''')
        
        # Create indices for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_calendar ON events (calendar_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_start ON events (start_datetime, start_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_end ON events (end_datetime, end_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_updated ON events (updated)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_cached ON events (cached_at)')
        
        # Create cache metadata table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        logger.info("Calendar cache database initialized successfully")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error initializing cache database: {e}")
        raise
    finally:
        conn.close()


def cache_events(events: List[Dict[str, Any]], calendar_id: str):
    """Cache events in the local database."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cached_at = datetime.now(timezone.utc).isoformat()
        
        for event in events:
            event_id = event.get('id')
            summary = event.get('summary', '')
            description = event.get('description', '')
            location = event.get('location', '')
            
            # Parse start/end times
            start = event.get('start', {})
            end = event.get('end', {})
            start_datetime = start.get('dateTime')
            end_datetime = end.get('dateTime')
            start_date = start.get('date')
            end_date = end.get('date')
            
            created = event.get('created')
            updated = event.get('updated')
            status = event.get('status', 'confirmed')
            transparency = event.get('transparency', 'opaque')
            visibility = event.get('visibility', 'default')
            
            # Store full event data as JSON
            event_data = json.dumps(event)
            
            cursor.execute("""
                INSERT OR REPLACE INTO events (
                    id, calendar_id, summary, description, location,
                    start_datetime, end_datetime, start_date, end_date,
                    created, updated, status, transparency, visibility,
                    event_data, cached_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id, calendar_id, summary, description, location,
                start_datetime, end_datetime, start_date, end_date,
                created, updated, status, transparency, visibility,
                event_data, cached_at
            ))
        
        # Update cache metadata
        cursor.execute("""
            INSERT OR REPLACE INTO cache_metadata (key, value, updated_at)
            VALUES (?, ?, ?)
        """, ('last_sync', calendar_id, cached_at))
        
        conn.commit()
        logger.info(f"Cached {len(events)} events for calendar {calendar_id}")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to cache events: {e}")
        raise
    finally:
        conn.close()


def get_cached_events(
    calendar_id: str = None,
    start_time: str = None,
    end_time: str = None,
    max_results: int = None,
    query: str = None
) -> List[Dict[str, Any]]:
    """Get cached events based on criteria."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Build WHERE conditions
        conditions = []
        params = []
        
        if calendar_id:
            conditions.append("calendar_id = ?")
            params.append(calendar_id)
        
        if start_time:
            conditions.append("(start_datetime >= ? OR start_date >= ?)")
            params.extend([start_time, start_time[:10]])  # Handle both datetime and date
        
        if end_time:
            conditions.append("(end_datetime <= ? OR end_date <= ?)")
            params.extend([end_time, end_time[:10]])
        
        if query:
            conditions.append("(summary LIKE ? OR description LIKE ?)")
            query_pattern = f"%{query}%"
            params.extend([query_pattern, query_pattern])
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        sql = f"""
            SELECT event_data FROM events 
            WHERE {where_clause}
            ORDER BY start_datetime ASC, start_date ASC
        """
        
        if max_results:
            sql += f" LIMIT {max_results}"
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        # Parse JSON event data
        events = []
        for row in rows:
            event_data = json.loads(row['event_data'])
            events.append(event_data)
        
        return events
        
    except Exception as e:
        logger.error(f"Failed to get cached events: {e}")
        raise
    finally:
        conn.close()


def get_events_within_minutes(minutes: int, calendar_id: str = None) -> List[Dict[str, Any]]:
    """Get events starting within the next N minutes."""
    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(minutes=minutes)).isoformat()
    
    return get_cached_events(
        calendar_id=calendar_id,
        start_time=time_min,
        end_time=time_max
    )


def clear_old_events(days_old: int = 30):
    """Clear events older than specified days from cache."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        cutoff_iso = cutoff_date.isoformat()
        
        cursor.execute("""
            DELETE FROM events 
            WHERE cached_at < ?
        """, (cutoff_iso,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        if deleted_count > 0:
            logger.info(f"Cleared {deleted_count} old events from cache")
            
    except Exception as e:
        conn.rollback()
        logger.error(f"Error clearing old events: {e}")
        raise
    finally:
        conn.close()
