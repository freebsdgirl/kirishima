"""
Calendar API Routes for FastAPI

This module defines the API endpoints for interacting with Google Calendar via Google's API.
It provides endpoints for creating, updating, deleting, and searching calendar events,
as well as managing calendar lists.

Endpoints:
    - POST /events: Create a new calendar event
    - PUT /events/{event_id}: Update an existing calendar event
    - DELETE /events/{event_id}: Delete a calendar event
    - GET /events/{event_id}: Get a specific event by ID
    - GET /events/upcoming: Get upcoming events
    - GET /events/today: Get today's events
    - GET /events/this-week: Get events for this week
    - GET /events/next-event: Get the next upcoming event
    - POST /events/search: Search events using various criteria
    - GET /events/date-range: Get events within a date range
    - GET /calendars: Get list of accessible calendars
    - GET /calendars/discover: Discover shared calendars
    - GET /calendars/current: Get current calendar info
    - POST /freebusy: Get free/busy information

All endpoints handle exceptions and return appropriate HTTP error responses.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from shared.models.googleapi import (
    CreateEventRequest,
    UpdateEventRequest,
    SearchEventsRequest,
    ApiResponse,
    CalendarEvent,  
    EventsListResponse,
    CalendarListResponse
)

from app.services.calendar.auth import get_calendar_service, get_calendar_id, discover_shared_calendars, validate_calendar_access, get_calendar_summary
from app.services.calendar.events import create_event, update_event, delete_event, get_event
from app.services.calendar.search import get_calendar_list, get_free_busy

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

router = APIRouter()


# Event management endpoints
@router.post("/events", response_model=ApiResponse)
async def create_event_endpoint(request: CreateEventRequest):
    """Create a new calendar event."""
    try:
        event = create_event(request)
        return ApiResponse(
            success=True,
            message="Event created successfully",
            data={
                'event_id': event.get('id'),
                'html_link': event.get('htmlLink'),
                'summary': event.get('summary')
            }
        )
    except Exception as e:
        logger.error(f"Failed to create event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create event: {str(e)}")


@router.put("/events/{event_id}", response_model=ApiResponse)
async def update_event_endpoint(event_id: str, request: UpdateEventRequest):
    """Update an existing calendar event."""
    try:
        # Set event_id from path parameter
        request.event_id = event_id
        
        event = update_event(request)
        return ApiResponse(
            success=True,
            message="Event updated successfully",
            data={
                'event_id': event.get('id'),
                'html_link': event.get('htmlLink'),
                'summary': event.get('summary')
            }
        )
    except Exception as e:
        logger.error(f"Failed to update event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update event: {str(e)}")


@router.delete("/events/{event_id}", response_model=ApiResponse)
async def delete_event_endpoint(event_id: str, send_notifications: bool = True):
    """Delete a calendar event."""
    try:
        success = delete_event(event_id, send_notifications)
        if success:
            return ApiResponse(
                success=True,
                message="Event deleted successfully",
                data={'event_id': event_id}
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to delete event")
    except Exception as e:
        logger.error(f"Failed to delete event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete event: {str(e)}")


@router.get("/events/{event_id}", response_model=CalendarEvent)
async def get_event_endpoint(event_id: str):
    """Get a specific event by ID."""
    try:
        event = get_event(event_id)
        return event
    except Exception as e:
        logger.error(f"Failed to get event {event_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Event not found: {str(e)}")


@router.get("/events/upcoming", response_model=List[CalendarEvent])
async def get_upcoming_events_endpoint(max_results: int = 10, days_ahead: int = 7):
    """Get upcoming events from Google Calendar API."""
    try:
        service = get_calendar_service()
        calendar_id = get_calendar_id()
        
        # Calculate time range
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days_ahead)).isoformat()
        
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        return [CalendarEvent(**event) for event in events]
    except Exception as e:
        logger.error(f"Failed to get upcoming events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get upcoming events: {str(e)}")


@router.get("/events/next-event", response_model=CalendarEvent)
async def get_next_event_endpoint():
    """Get the next upcoming event."""
    try:
        service = get_calendar_service()
        calendar_id = get_calendar_id()
        
        # Get events starting from now
        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            maxResults=1,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        if events:
            return CalendarEvent(**events[0])
        else:
            raise HTTPException(status_code=404, detail="No upcoming events found")
    except Exception as e:
        logger.error(f"Failed to get next event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get next event: {str(e)}")


@router.get("/events/today", response_model=List[CalendarEvent])
async def get_today_events_endpoint():
    """Get events for today from Google Calendar API."""
    try:
        service = get_calendar_service()
        calendar_id = get_calendar_id()
        
        # Calculate today's date range
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        return [CalendarEvent(**event) for event in events]
    except Exception as e:
        logger.error(f"Failed to get today's events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get today's events: {str(e)}")


@router.get("/events/this-week", response_model=List[CalendarEvent])
async def get_this_week_events_endpoint():
    """Get events for this week from Google Calendar API."""
    try:
        service = get_calendar_service()
        calendar_id = get_calendar_id()
        
        # Calculate this week's date range
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_week = start_of_week + timedelta(days=7)
        
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_of_week.isoformat(),
            timeMax=end_of_week.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        return [CalendarEvent(**event) for event in events]
    except Exception as e:
        logger.error(f"Failed to get this week's events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get this week's events: {str(e)}")


# Search endpoints
@router.post("/events/search", response_model=EventsListResponse)
async def search_events_endpoint(request: SearchEventsRequest):
    """Search events using Google Calendar API."""
    try:
        service = get_calendar_service()
        calendar_id = get_calendar_id()
        
        # Build API parameters
        params = {
            'calendarId': calendar_id,
            'singleEvents': True,
            'orderBy': 'startTime'
        }
        
        if request.time_min:
            params['timeMin'] = request.time_min
        if request.time_max:
            params['timeMax'] = request.time_max
        if request.max_results:
            params['maxResults'] = request.max_results
        if request.q:
            params['q'] = request.q
        
        events_result = service.events().list(**params).execute()
        events = events_result.get('items', [])
        
        # Convert to CalendarEvent objects
        calendar_events = [CalendarEvent(**event) for event in events]
        
        return EventsListResponse(
            events=calendar_events,
            next_page_token=events_result.get('nextPageToken'),
            kind="calendar#events"
        )
    except Exception as e:
        logger.error(f"Failed to search events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search events: {str(e)}")


@router.get("/events/date-range", response_model=List[CalendarEvent])
async def get_events_by_date_range_endpoint(start_date: str, end_date: str, max_results: int = 100):
    """Get events within a date range from Google Calendar API."""
    try:
        service = get_calendar_service()
        calendar_id = get_calendar_id()
        
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_date,
            timeMax=end_date,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        return [CalendarEvent(**event) for event in events]
    except Exception as e:
        logger.error(f"Failed to get events by date range: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get events by date range: {str(e)}")


# Calendar management endpoints
@router.get("/calendars", response_model=CalendarListResponse)
async def get_calendar_list_endpoint():
    """Get list of accessible calendars."""
    try:
        calendars = get_calendar_list()
        return calendars
    except Exception as e:
        logger.error(f"Failed to get calendar list: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get calendar list: {str(e)}")


@router.get("/calendars/current", response_model=Dict[str, Any])
async def get_current_calendar_endpoint():
    """Get information about the currently configured calendar."""
    try:
        calendar_id = get_calendar_id()
        calendar_info = validate_calendar_access()
        
        return {
            'success': True,
            'message': 'Current calendar information retrieved successfully',
            'data': {
                'calendar_id': calendar_id,
                'summary': calendar_info.get('summary'),
                'description': calendar_info.get('description'),
                'location': calendar_info.get('location'),
                'timeZone': calendar_info.get('timeZone'),
                'access_role': calendar_info.get('accessRole', 'Unknown'),
                'primary': calendar_info.get('primary', False)
            }
        }
    except Exception as e:
        logger.error(f"Failed to get current calendar info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get current calendar info: {str(e)}")


@router.get("/calendars/discover", response_model=Dict[str, Any])
async def discover_shared_calendars_endpoint():
    """Discover shared calendars the user has access to."""
    try:
        calendars = discover_shared_calendars()
        
        # Highlight the currently configured calendar if any
        current_calendar_id = None
        try:
            current_calendar_id = get_calendar_id()
        except ValueError:
            # No calendar configured yet
            pass
        
        return {
            'success': True,
            'message': f'Discovered {len(calendars)} calendars',
            'data': {
                'calendars': calendars,
                'current_calendar_id': current_calendar_id,
                'total_calendars': len(calendars)
            }
        }
    except Exception as e:
        logger.error(f"Failed to discover shared calendars: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to discover shared calendars: {str(e)}")


@router.post("/freebusy", response_model=Dict[str, Any])
async def get_free_busy_endpoint(
    time_min: str,
    time_max: str,
    calendars: Optional[List[str]] = None
):
    """Get free/busy information for calendars."""
    try:
        freebusy_info = get_free_busy(time_min, time_max, calendars)
        return {
            'success': True,
            'message': 'Free/busy information retrieved successfully',
            'data': freebusy_info
        }
    except Exception as e:
        logger.error(f"Failed to get free/busy information: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get free/busy information: {str(e)}")



