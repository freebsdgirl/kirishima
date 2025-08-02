"""
Calendar monitoring utilities.

This module provides functions for background monitoring of calendar events,
caching them locally, and detecting changes (new, updated, deleted events).

Functions:
    start_calendar_monitoring(): Start background calendar monitoring
    stop_calendar_monitoring(): Stop background calendar monitoring  
    get_monitor_status(): Get current monitoring status
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from app.services.calendar.auth import get_calendar_service, get_calendar_id
from app.services.calendar.cache import init_cache_db, cache_events, get_cached_events
from app.services.gmail.util import get_config
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List


# Global monitoring state
_monitoring_task = None


async def start_calendar_monitoring():
    """
    Start monitoring calendar events and caching them locally.
    """
    global _monitoring_task
    
    if _monitoring_task and not _monitoring_task.done():
        logger.warning("Calendar monitoring is already running")
        return
    
    config = get_config()
    calendar_config = config.get('calendar', {}).get('monitor', {})
    
    if not calendar_config.get('enabled', False):
        logger.info("Calendar monitoring is disabled in config")
        return
    
    try:
        # Initialize cache database
        init_cache_db()
        
        # Start monitoring
        logger.info("Starting calendar monitoring")
        _monitoring_task = asyncio.create_task(_monitor_calendar_events())
            
    except Exception as e:
        logger.error(f"Failed to start calendar monitoring: {e}")
        raise


async def stop_calendar_monitoring():
    """
    Stop calendar monitoring and clean up resources.
    """
    global _monitoring_task
    
    if _monitoring_task and not _monitoring_task.done():
        _monitoring_task.cancel()
        try:
            await _monitoring_task
        except asyncio.CancelledError:
            pass
        logger.info("Calendar monitoring stopped")


async def _monitor_calendar_events():
    """
    Monitor calendar events and cache them locally.
    """
    config = get_config()
    calendar_config = config.get('calendar', {}).get('monitor', {})
    poll_interval = calendar_config.get('poll_interval', 300)  # 5 minutes default
    
    logger.info(f"Calendar monitoring started - polling every {poll_interval}s")
    
    while True:
        try:
            await _sync_calendar_events()
            await asyncio.sleep(poll_interval)
            
        except asyncio.CancelledError:
            logger.info("Calendar monitoring cancelled")
            break
        except Exception as e:
            logger.error(f"Error in calendar monitoring: {e}")
            await asyncio.sleep(30)  # Short retry delay


async def _sync_calendar_events():
    """
    Sync calendar events from Google Calendar API to local cache.
    """
    try:
        service = get_calendar_service()
        calendar_id = get_calendar_id()
        
        # Get events from the past week to next month
        now = datetime.now(timezone.utc)
        time_min = (now - timedelta(days=7)).isoformat()
        time_max = (now + timedelta(days=30)).isoformat()
        
        logger.debug(f"Syncing events from {time_min} to {time_max}")
        
        # Fetch events from Google Calendar
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime',
            maxResults=2500  # High limit to get all events
        ).execute()
        
        events = events_result.get('items', [])
        
        logger.info(f"Fetched {len(events)} events from Google Calendar")
        
        # Get currently cached events for comparison
        cached_events = get_cached_events(
            calendar_id=calendar_id,
            start_time=time_min,
            end_time=time_max
        )
        
        # Detect changes
        _detect_event_changes(events, cached_events)
        
        # Cache the events
        cache_events(events, calendar_id)
        
    except Exception as e:
        logger.error(f"Failed to sync calendar events: {e}")


def _detect_event_changes(new_events: List[Dict[str, Any]], cached_events: List[Dict[str, Any]]):
    """
    Detect changes between new events and cached events.
    """
    try:
        # Create lookups by event ID
        new_by_id = {event.get('id'): event for event in new_events}
        cached_by_id = {event.get('id'): event for event in cached_events}
        
        # Find new events
        new_event_ids = set(new_by_id.keys()) - set(cached_by_id.keys())
        if new_event_ids:
            logger.info(f"Detected {len(new_event_ids)} new events")
            for event_id in new_event_ids:
                event = new_by_id[event_id]
                logger.debug(f"New event: {event.get('summary', 'No title')} ({event_id})")
        
        # Find deleted events
        deleted_event_ids = set(cached_by_id.keys()) - set(new_by_id.keys())
        if deleted_event_ids:
            logger.info(f"Detected {len(deleted_event_ids)} deleted events")
            for event_id in deleted_event_ids:
                event = cached_by_id[event_id]
                logger.debug(f"Deleted event: {event.get('summary', 'No title')} ({event_id})")
        
        # Find updated events
        updated_events = []
        for event_id in set(new_by_id.keys()) & set(cached_by_id.keys()):
            new_event = new_by_id[event_id]
            cached_event = cached_by_id[event_id]
            
            # Compare updated timestamps
            new_updated = new_event.get('updated')
            cached_updated = cached_event.get('updated')
            
            if new_updated != cached_updated:
                updated_events.append(event_id)
                logger.debug(f"Updated event: {new_event.get('summary', 'No title')} ({event_id})")
        
        if updated_events:
            logger.info(f"Detected {len(updated_events)} updated events")
            
    except Exception as e:
        logger.error(f"Error detecting event changes: {e}")


def get_monitor_status() -> Dict[str, Any]:
    """
    Get the current status of calendar monitoring.
    
    Returns:
        Dict containing monitoring status information
    """
    global _monitoring_task
    
    config = get_config()
    calendar_config = config.get('calendar', {}).get('monitor', {})
    
    status = {
        'monitoring_active': _monitoring_task is not None and not _monitoring_task.done(),
        'poll_interval': calendar_config.get('poll_interval', 300),
        'notification_minutes': calendar_config.get('notification_minutes', 30),
        'enabled': calendar_config.get('enabled', False)
    }
    
    return status
