"""
Calendar search and query utilities.

This module provides functions for searching and querying calendar events
using various criteria and filters.

Functions:
    search_events(): Search events using various criteria
    get_events_by_date_range(): Get events within a specific date range
    get_today_events(): Get events for today
    get_calendar_list(): Get list of accessible calendars
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from shared.models.googleapi import SearchEventsRequest, CalendarEvent, EventsListResponse, CalendarListResponse
from app.services.calendar.auth import get_calendar_service, get_calendar_id
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta


def search_events(request: SearchEventsRequest) -> EventsListResponse:
    """
    Search calendar events using various criteria.
    
    Args:
        request: SearchEventsRequest with search parameters
        
    Returns:
        EventsListResponse: Search results
        
    Raises:
        Exception: If search fails
    """
    try:
        service = get_calendar_service()
        calendar_id = get_calendar_id()
        
        # Build search parameters
        params = {
            'calendarId': calendar_id,
            'maxResults': request.max_results,
            'orderBy': request.order_by,
            'singleEvents': request.single_events,
            'showDeleted': request.show_deleted
        }
        
        if request.q:
            params['q'] = request.q
            
        if request.time_min:
            params['timeMin'] = request.time_min
            
        if request.time_max:
            params['timeMax'] = request.time_max
        
        # Execute search
        events_result = service.events().list(**params).execute()
        
        events = events_result.get('items', [])
        next_page_token = events_result.get('nextPageToken')
        updated = events_result.get('updated')
        
        logger.info(f"Found {len(events)} events matching search criteria")
        
        # Convert to CalendarEvent models
        calendar_events = [CalendarEvent(**event) for event in events]
        
        return EventsListResponse(
            events=calendar_events,
            next_page_token=next_page_token,
            updated=updated
        )
        
    except Exception as e:
        logger.error(f"Failed to search events: {e}")
        raise


def get_events_by_date_range(start_date: str, end_date: str, max_results: int = 100) -> List[CalendarEvent]:
    """
    Get events within a specific date range.
    
    Args:
        start_date: Start date in ISO 8601 format
        end_date: End date in ISO 8601 format
        max_results: Maximum number of events to return
        
    Returns:
        List[CalendarEvent]: Events within the date range
    """
    try:
        request = SearchEventsRequest(
            time_min=start_date,
            time_max=end_date,
            max_results=max_results,
            order_by='startTime'
        )
        
        response = search_events(request)
        return response.events
        
    except Exception as e:
        logger.error(f"Failed to get events by date range: {e}")
        raise


def get_today_events() -> List[CalendarEvent]:
    """
    Get events for today.
    
    Returns:
        List[CalendarEvent]: Today's events
    """
    try:
        # Calculate today's date range
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        return get_events_by_date_range(
            start_of_day.isoformat(),
            end_of_day.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to get today's events: {e}")
        raise


def get_calendar_list() -> CalendarListResponse:
    """
    Get list of accessible calendars.
    
    Returns:
        CalendarListResponse: List of calendars
    """
    try:
        service = get_calendar_service()
        
        calendar_list_result = service.calendarList().list().execute()
        
        calendars = calendar_list_result.get('items', [])
        next_page_token = calendar_list_result.get('nextPageToken')
        
        logger.info(f"Retrieved {len(calendars)} calendars")
        
        return CalendarListResponse(
            calendars=calendars,
            next_page_token=next_page_token
        )
        
    except Exception as e:
        logger.error(f"Failed to get calendar list: {e}")
        raise


def get_free_busy(time_min: str, time_max: str, calendars: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Get free/busy information for calendars.
    
    Args:
        time_min: Start time in ISO 8601 format
        time_max: End time in ISO 8601 format
        calendars: List of calendar IDs (defaults to current calendar)
        
    Returns:
        Dict containing free/busy information
    """
    try:
        service = get_calendar_service()
        
        if calendars is None:
            calendars = [get_calendar_id()]
        
        # Build request body
        body = {
            'timeMin': time_min,
            'timeMax': time_max,
            'items': [{'id': cal_id} for cal_id in calendars]
        }
        
        freebusy_result = service.freebusy().query(body=body).execute()
        
        logger.info(f"Retrieved free/busy information for {len(calendars)} calendars")
        
        return freebusy_result
        
    except Exception as e:
        logger.error(f"Failed to get free/busy information: {e}")
        raise


def get_upcoming_events(max_results: int = 10, days_ahead: int = 7) -> EventsListResponse:
    """
    Get upcoming events from the calendar cache.
    
    Args:
        max_results: Maximum number of events to return
        days_ahead: Number of days ahead to look for events
        
    Returns:
        EventsListResponse: List of upcoming events
        
    Raises:
        Exception: If retrieving events fails
    """
    try:
        from app.services.calendar.auth import get_calendar_id
        from app.services.calendar.cache import get_cached_events
        
        calendar_id = get_calendar_id()
        
        # Calculate time range
        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days_ahead)).isoformat()
        
        events_data = get_cached_events(
            calendar_id=calendar_id,
            start_time=time_min,
            end_time=time_max,
            max_results=max_results
        )
        
        events = [CalendarEvent(**event) for event in events_data]
        
        logger.info(f"Retrieved {len(events)} upcoming events from cache")
        
        return EventsListResponse(events=events)
        
    except Exception as e:
        logger.error(f"Failed to get upcoming events: {e}")
        raise
