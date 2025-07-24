"""
Calendar cache management for local SQLite storage.

This module provides functions for caching calendar events locally to improve
response times and reduce Google API calls. The cache is updated via background
monitoring and serves data to the calendar endpoints.

Functions:
    init_cache_db(): Initialize the calendar cache database
    cache_events(): Store events in the local cache
    get_cached_events(): Retrieve events from cache
    get_cache_stats(): Get cache statistics
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from app.services.gmail.util import get_config
import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path


def init_cache_db():
    """
    Initialize the calendar cache database with required tables.
    """
    try:
        config = get_config()
        db_path = config.get('db', {}).get('googleapi_calendar')
        
        if not db_path:
            raise ValueError("googleapi_calendar database path not configured")
        
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
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
                    event_data TEXT,
                    cached_at TEXT NOT NULL,
                    FOREIGN KEY (calendar_id) REFERENCES calendars(id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS calendars (
                    id TEXT PRIMARY KEY,
                    summary TEXT,
                    description TEXT,
                    access_role TEXT,
                    primary_calendar INTEGER DEFAULT 0,
                    cached_at TEXT NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Create indexes for better query performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_calendar_id ON events(calendar_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_start_datetime ON events(start_datetime)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_end_datetime ON events(end_datetime)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_updated ON events(updated)")
            
            conn.commit()
            logger.info("Calendar cache database initialized successfully")
            
    except Exception as e:
        logger.error(f"Failed to initialize calendar cache database: {e}")
        raise


def cache_events(events: List[Dict[str, Any]], calendar_id: str):
    """
    Store events in the local cache database.
    
    Args:
        events: List of event dictionaries from Google Calendar API
        calendar_id: Calendar ID the events belong to
    """
    try:
        config = get_config()
        db_path = config.get('db', {}).get('googleapi_calendar')
        
        if not db_path:
            raise ValueError("googleapi_calendar database path not configured")
        
        cached_at = datetime.now(timezone.utc).isoformat()
        
        with sqlite3.connect(db_path) as conn:
            # Clear existing events for this calendar (full refresh)
            conn.execute("DELETE FROM events WHERE calendar_id = ?", (calendar_id,))
            
            for event in events:
                # Extract event fields
                event_id = event.get('id')
                summary = event.get('summary', '')
                description = event.get('description', '')
                location = event.get('location', '')
                
                # Handle start/end times
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
                
                # Store full event data as JSON for complete information
                event_data = json.dumps(event)
                
                conn.execute("""
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
            conn.execute("""
                INSERT OR REPLACE INTO cache_metadata (key, value, updated_at)
                VALUES (?, ?, ?)
            """, ('last_sync', calendar_id, cached_at))
            
            conn.commit()
            logger.info(f"Cached {len(events)} events for calendar {calendar_id}")
            
    except Exception as e:
        logger.error(f"Failed to cache events: {e}")
        raise


def get_cached_events(
    calendar_id: str = None,
    start_time: str = None,
    end_time: str = None,
    max_results: int = None,
    query: str = None
) -> List[Dict[str, Any]]:
    """
    Retrieve events from the local cache.
    
    Args:
        calendar_id: Filter by calendar ID
        start_time: Filter events starting after this time (ISO format)
        end_time: Filter events ending before this time (ISO format)
        max_results: Limit number of results
        query: Text search in summary/description
        
    Returns:
        List of event dictionaries
    """
    try:
        config = get_config()
        db_path = config.get('db', {}).get('googleapi_calendar')
        
        if not db_path:
            raise ValueError("googleapi_calendar database path not configured")
        
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row  # Enable column access by name
            
            # Build query
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
            
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            
            # Parse JSON event data
            events = []
            for row in rows:
                try:
                    event_data = json.loads(row['event_data'])
                    events.append(event_data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse cached event data: {e}")
                    continue
            
            logger.debug(f"Retrieved {len(events)} cached events")
            return events
            
    except Exception as e:
        logger.error(f"Failed to retrieve cached events: {e}")
        return []


def get_cache_stats() -> Dict[str, Any]:
    """
    Get statistics about the calendar cache.
    
    Returns:
        Dictionary with cache statistics
    """
    try:
        config = get_config()
        db_path = config.get('db', {}).get('googleapi_calendar')
        
        if not db_path:
            return {"error": "Cache database not configured"}
        
        if not Path(db_path).exists():
            return {"error": "Cache database not initialized"}
        
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Get event counts
            cursor = conn.execute("SELECT COUNT(*) as total_events FROM events")
            total_events = cursor.fetchone()['total_events']
            
            # Get calendar count
            cursor = conn.execute("SELECT COUNT(*) as total_calendars FROM calendars")
            total_calendars = cursor.fetchone()['total_calendars']
            
            # Get last sync time
            cursor = conn.execute("""
                SELECT value, updated_at FROM cache_metadata 
                WHERE key = 'last_sync' 
                ORDER BY updated_at DESC LIMIT 1
            """)
            last_sync_row = cursor.fetchone()
            last_sync = last_sync_row['updated_at'] if last_sync_row else None
            
            return {
                "total_events": total_events,
                "total_calendars": total_calendars,
                "last_sync": last_sync,
                "database_path": db_path
            }
            
    except Exception as e:
        logger.error(f"Failed to get cache statistics: {e}")
        return {"error": str(e)}
