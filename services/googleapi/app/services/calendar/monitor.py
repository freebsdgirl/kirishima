"""
Calendar push notifications and monitoring utilities.

This module provides functions for setting up and managing push notifications
for calendar changes, as well as polling-based monitoring as a fallback.

Functions:
    start_calendar_monitoring(): Start monitoring calendar changes
    stop_calendar_monitoring(): Stop monitoring calendar changes
    setup_push_notifications(): Set up push notification webhooks
    handle_calendar_notification(): Handle incoming push notifications
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from app.services.calendar.auth import get_calendar_service, get_calendar_id
from app.services.gmail.util import get_config
from typing import Dict, Any, Optional
import asyncio
import httpx
import uuid
import json
from datetime import datetime, timezone, timedelta, timedelta

# Global monitoring state
_monitoring_task = None
_notification_channels = {}


async def start_calendar_monitoring():
    """
    Start monitoring calendar changes using either push notifications or polling.
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
        # Try to set up push notifications first
        if calendar_config.get('push_notifications', {}).get('enabled', False):
            logger.info("Setting up push notifications for calendar monitoring")
            await setup_push_notifications()
        else:
            # Fall back to polling
            logger.info("Starting calendar polling monitoring")
            _monitoring_task = asyncio.create_task(_poll_calendar_changes())
            
    except Exception as e:
        logger.error(f"Failed to start calendar monitoring: {e}")
        # Fall back to polling if push notifications fail
        logger.info("Falling back to polling mode")
        _monitoring_task = asyncio.create_task(_poll_calendar_changes())


def stop_calendar_monitoring():
    """
    Stop calendar monitoring and clean up resources.
    """
    global _monitoring_task, _notification_channels
    
    if _monitoring_task and not _monitoring_task.done():
        _monitoring_task.cancel()
        logger.info("Calendar monitoring stopped")
    
    # Stop any active notification channels
    for channel_id, channel_info in _notification_channels.items():
        try:
            _stop_notification_channel(channel_id, channel_info['resourceId'])
        except Exception as e:
            logger.error(f"Failed to stop notification channel {channel_id}: {e}")
    
    _notification_channels.clear()


async def setup_push_notifications():
    """
    Set up push notification webhooks for calendar changes.
    """
    try:
        service = get_calendar_service()
        calendar_id = get_calendar_id()
        config = get_config()
        
        push_config = config.get('calendar', {}).get('monitor', {}).get('push_notifications', {})
        webhook_url = push_config.get('webhook_url')
        
        if not webhook_url:
            raise ValueError("webhook_url not configured for calendar push notifications")
        
        # Create a unique channel ID
        channel_id = str(uuid.uuid4())
        
        # Set up the watch request
        watch_request = {
            'id': channel_id,
            'type': 'web_hook',
            'address': webhook_url,
            'token': f'calendar-{channel_id}'
        }
        
        # Set expiration if configured (max 30 days)
        expiration_hours = push_config.get('expiration_hours', 24)
        if expiration_hours:
            expiration_ms = int((datetime.now(timezone.utc).timestamp() + (expiration_hours * 3600)) * 1000)
            watch_request['expiration'] = expiration_ms
        
        # Create the notification channel
        response = service.events().watch(
            calendarId=calendar_id,
            body=watch_request
        ).execute()
        
        # Store channel information for cleanup
        _notification_channels[channel_id] = {
            'resourceId': response.get('resourceId'),
            'expiration': response.get('expiration'),
            'calendarId': calendar_id
        }
        
        logger.info(f"Set up push notifications for calendar {calendar_id}, channel: {channel_id}")
        
    except Exception as e:
        logger.error(f"Failed to set up push notifications: {e}")
        raise


def _stop_notification_channel(channel_id: str, resource_id: str):
    """
    Stop a specific notification channel.
    """
    try:
        service = get_calendar_service()
        
        stop_request = {
            'id': channel_id,
            'resourceId': resource_id
        }
        
        service.channels().stop(body=stop_request).execute()
        logger.info(f"Stopped notification channel: {channel_id}")
        
    except Exception as e:
        logger.error(f"Failed to stop notification channel {channel_id}: {e}")
        raise


async def handle_calendar_notification(headers: Dict[str, str], body: str = "") -> Dict[str, Any]:
    """
    Handle incoming calendar push notifications.
    
    Args:
        headers: HTTP headers from the notification request
        body: Request body (usually empty for calendar notifications)
        
    Returns:
        Dict containing processing status
    """
    try:
        # Extract notification information from headers
        channel_id = headers.get('X-Goog-Channel-ID')
        resource_state = headers.get('X-Goog-Resource-State')
        resource_id = headers.get('X-Goog-Resource-ID')
        message_number = headers.get('X-Goog-Message-Number')
        
        logger.info(f"Received calendar notification - Channel: {channel_id}, "
                   f"State: {resource_state}, Message: {message_number}")
        
        # Handle sync message (initial confirmation)
        if resource_state == 'sync':
            logger.info(f"Calendar notification sync confirmed for channel: {channel_id}")
            return {'status': 'sync_confirmed', 'channel_id': channel_id}
        
        # Handle actual change notifications
        if resource_state == 'exists':
            logger.info(f"Calendar change detected for channel: {channel_id}")
            
            # Forward to brain service if configured
            await _forward_calendar_change_to_brain(channel_id, resource_id)
            
            return {'status': 'change_processed', 'channel_id': channel_id}
        
        logger.warning(f"Unknown resource state: {resource_state}")
        return {'status': 'unknown_state', 'resource_state': resource_state}
        
    except Exception as e:
        logger.error(f"Failed to handle calendar notification: {e}")
        return {'status': 'error', 'error': str(e)}


async def _poll_calendar_changes():
    """
    Poll for calendar changes periodically (fallback method).
    """
    config = get_config()
    poll_interval = config.get('calendar', {}).get('monitor', {}).get('poll_interval', 300)  # 5 minutes default
    
    last_sync_token = None
    
    while True:
        try:
            service = get_calendar_service()
            calendar_id = get_calendar_id()
            
            # Use incremental sync if we have a sync token
            params = {'calendarId': calendar_id}
            if last_sync_token:
                params['syncToken'] = last_sync_token
            else:
                # Initial sync - get events from last week to now
                now = datetime.now(timezone.utc)
                week_ago = now - timedelta(days=7)
                params['timeMin'] = week_ago.isoformat()
                params['singleEvents'] = True
                params['orderBy'] = 'startTime'
            
            events_result = service.events().list(**params).execute()
            
            events = events_result.get('items', [])
            new_sync_token = events_result.get('nextSyncToken')
            
            if events and last_sync_token:  # Only process if we had a previous sync token (not initial sync)
                logger.info(f"Detected {len(events)} calendar changes via polling")
                await _forward_calendar_changes_to_brain(events)
            
            if new_sync_token:
                last_sync_token = new_sync_token
            
            await asyncio.sleep(poll_interval)
            
        except Exception as e:
            logger.error(f"Error in calendar polling: {e}")
            await asyncio.sleep(poll_interval)


async def _forward_calendar_change_to_brain(channel_id: str, resource_id: str):
    """
    Forward calendar change notification to brain service.
    """
    try:
        config = get_config()
        brain_url = config.get('calendar', {}).get('monitor', {}).get('brain_url')
        
        if not brain_url:
            logger.warning("brain_url not configured for calendar monitoring")
            return
        
        notification_data = {
            'type': 'calendar_change',
            'channel_id': channel_id,
            'resource_id': resource_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': 'googleapi_calendar'
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                brain_url,
                json=notification_data,
                timeout=10.0
            )
            
            if response.status_code == 200:
                logger.info(f"Calendar change forwarded to brain service")
            else:
                logger.warning(f"Brain service responded with status {response.status_code}")
                
    except Exception as e:
        logger.error(f"Failed to forward calendar change to brain: {e}")


async def _forward_calendar_changes_to_brain(events: list):
    """
    Forward multiple calendar changes to brain service (polling mode).
    """
    try:
        config = get_config()
        brain_url = config.get('calendar', {}).get('monitor', {}).get('brain_url')
        
        if not brain_url:
            logger.warning("brain_url not configured for calendar monitoring")
            return
        
        notification_data = {
            'type': 'calendar_changes',
            'events_count': len(events),
            'events': events,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': 'googleapi_calendar_poll'
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                brain_url,
                json=notification_data,
                timeout=10.0
            )
            
            if response.status_code == 200:
                logger.info(f"Calendar changes forwarded to brain service")
            else:
                logger.warning(f"Brain service responded with status {response.status_code}")
                
    except Exception as e:
        logger.error(f"Failed to forward calendar changes to brain: {e}")


def get_monitor_status() -> Dict[str, Any]:
    """
    Get the current status of calendar monitoring.
    
    Returns:
        Dict containing monitoring status information
    """
    global _monitoring_task, _notification_channels
    
    status = {
        'monitoring_active': _monitoring_task is not None and not _monitoring_task.done(),
        'notification_channels': len(_notification_channels),
        'channels': []
    }
    
    for channel_id, channel_info in _notification_channels.items():
        status['channels'].append({
            'channel_id': channel_id,
            'calendar_id': channel_info.get('calendarId'),
            'expiration': channel_info.get('expiration')
        })
    
    return status
