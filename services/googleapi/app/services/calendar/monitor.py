"""
Calendar reminder monitoring utilities.

This module provides functions for background monitoring of upcoming calendar
events and creating notifications when events are approaching their start time.

Functions:
    start_calendar_monitoring(): Start background calendar reminder monitoring
    stop_calendar_monitoring(): Stop background calendar reminder monitoring  
    get_monitor_status(): Get current monitoring status
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from app.services.calendar.auth import get_calendar_service, get_calendar_id
from app.services.gmail.util import get_config
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional


# Global monitoring state
_monitoring_task = None


async def start_calendar_monitoring():
    """
    Start monitoring upcoming calendar events for reminders.
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
        # Start reminder monitoring
        logger.info("Starting calendar reminder monitoring")
        _monitoring_task = asyncio.create_task(_check_upcoming_events())
            
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


async def _check_upcoming_events():
    """
    Check for upcoming calendar events and create notifications.
    """
    config = get_config()
    calendar_config = config.get('calendar', {}).get('monitor', {})
    poll_interval = calendar_config.get('poll_interval', 300)  # 5 minutes default
    notification_minutes = calendar_config.get('notification_minutes', 30)  # 30 minutes default
    
    logger.info(f"Calendar reminder monitoring started - checking every {poll_interval}s for events in next {notification_minutes} minutes")
    
    while True:
        try:
            await _process_upcoming_events(notification_minutes)
            await asyncio.sleep(poll_interval)
            
        except asyncio.CancelledError:
            logger.info("Calendar reminder monitoring cancelled")
            break
        except Exception as e:
            logger.error(f"Error in calendar reminder monitoring: {e}")
            await asyncio.sleep(30)  # Short retry delay


async def _process_upcoming_events(notification_minutes: int):
    """
    Process upcoming events and create notifications for events starting soon.
    """
    try:
        service = get_calendar_service()
        calendar_id = get_calendar_id()
        
        # Calculate time window for upcoming events
        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(minutes=notification_minutes)).isoformat()
        
        logger.debug(f"Checking for events between {time_min} and {time_max}")
        
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if events:
            logger.info(f"Found {len(events)} upcoming events in next {notification_minutes} minutes")
            await _create_event_reminders(events, notification_minutes)
        else:
            logger.debug("No upcoming events found")
            
    except Exception as e:
        logger.error(f"Failed to process upcoming events: {e}")


async def _create_event_reminders(events: list, notification_minutes: int):
    """
    Create reminder notifications for upcoming events.
    """
    try:
        from app.services.calendar.notifications import cache_notification, get_pending_notifications
        
        now = datetime.now(timezone.utc)
        
        for event in events:
            # Skip cancelled events
            if event.get('status') == 'cancelled':
                continue
                
            event_id = event.get('id')
            event_start = event.get('start', {})
            
            # Parse event start time
            start_time = None
            if 'dateTime' in event_start:
                # Handle different timezone formats from Google Calendar API
                date_time_str = event_start['dateTime']
                try:
                    # Try parsing with timezone info first
                    if date_time_str.endswith('Z'):
                        start_time = datetime.fromisoformat(date_time_str.replace('Z', '+00:00'))
                    else:
                        start_time = datetime.fromisoformat(date_time_str)
                except ValueError:
                    # Fallback: try parsing as UTC if no timezone info
                    try:
                        start_time = datetime.fromisoformat(date_time_str.replace('Z', '+00:00'))
                    except ValueError:
                        logger.warning(f"Could not parse datetime format: {date_time_str}")
                        continue
            elif 'date' in event_start:
                # All-day event
                try:
                    start_time = datetime.fromisoformat(event_start['date']).replace(tzinfo=timezone.utc)
                except ValueError:
                    logger.warning(f"Could not parse date format: {event_start['date']}")
                    continue
            
            if not start_time:
                logger.warning(f"Could not parse start time for event {event_id}")
                continue
            
            # Calculate minutes until event starts
            minutes_until_start = int((start_time - now).total_seconds() / 60)
            
            # Only create notification if event is starting within the notification window
            if 0 <= minutes_until_start <= notification_minutes:
                # Check if we've already created a notification for this event
                existing_notifications = get_pending_notifications(
                    notification_type='calendar_reminder',
                    source='googleapi_calendar_reminder'
                )
                
                # Check if we already have a notification for this event
                event_already_notified = any(
                    n['data'].get('event_id') == event_id 
                    for n in existing_notifications
                )
                
                if not event_already_notified:
                    # Create reminder notification
                    notification_data = {
                        'type': 'calendar_reminder',
                        'event_id': event_id,
                        'summary': event.get('summary', 'No title'),
                        'start_time': start_time.isoformat(),
                        'minutes_until_start': minutes_until_start,
                        'location': event.get('location', ''),
                        'description': event.get('description', ''),
                        'html_link': event.get('htmlLink', ''),
                        'timestamp': now.isoformat(),
                        'source': 'googleapi_calendar_reminder'
                    }
                    
                    notification_id = cache_notification(
                        notification_type='calendar_reminder',
                        source='googleapi_calendar_reminder',
                        data=notification_data
                    )
                    
                    logger.info(f"Created reminder notification {notification_id} for event '{event.get('summary')}' starting in {minutes_until_start} minutes")
                else:
                    logger.debug(f"Event {event_id} already has a pending notification")
                    
    except Exception as e:
        logger.error(f"Failed to create event reminders: {e}")


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
        'reminder_enabled': calendar_config.get('enabled', False)
    }
    
    return status
