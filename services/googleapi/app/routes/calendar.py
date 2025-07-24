"""
Calendar API Routes for FastAPI

This module defines the API endpoints for interacting with Google Calendar via Google's API.
It provides endpoints for creating, updating, deleting, and searching calendar events,
as well as managing calendar lists and monitoring calendar changes.

Endpoints:
    - POST /events: Create a new calendar event
    - PUT /events/{event_id}: Update an existing calendar event
    - DELETE /events/{event_id}: Delete a calendar event
    - GET /events/{event_id}: Get a specific event by ID
    - GET /events/upcoming: Get upcoming events
    - GET /events/today: Get today's events
    - POST /events/search: Search events using various criteria
    - GET /events/date-range: Get events within a date range
    - GET /calendars: Get list of accessible calendars
    - GET /calendars/discover: Discover shared calendars
    - POST /freebusy: Get free/busy information
    - POST /monitor/start: Start calendar monitoring
    - POST /monitor/stop: Stop calendar monitoring
    - GET /monitor/status: Get calendar monitoring status
    - POST /webhook/notifications: Handle incoming push notifications

All endpoints handle exceptions and return appropriate HTTP error responses.
"""

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response

from shared.models.googleapi import (
    CreateEventRequest,
    UpdateEventRequest,
    SearchEventsRequest,
    CalendarResponse,
    CalendarEvent,  
    EventsListResponse,
    CalendarListResponse
)

from app.services.calendar.auth import get_calendar_service, get_calendar_id, discover_shared_calendars, validate_calendar_access, get_calendar_summary
from app.services.calendar.events import create_event, update_event, delete_event, get_event, get_upcoming_events
from app.services.calendar.search import search_events, get_events_by_date_range, get_today_events, get_calendar_list, get_free_busy
from app.services.calendar.monitor import start_calendar_monitoring, stop_calendar_monitoring, get_monitor_status, handle_calendar_notification

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

router = APIRouter()


# Event management endpoints
@router.post("/events", response_model=CalendarResponse)
async def create_event_endpoint(request: CreateEventRequest):
    """Create a new calendar event."""
    try:
        event = create_event(request)
        return CalendarResponse(
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


@router.put("/events/{event_id}", response_model=CalendarResponse)
async def update_event_endpoint(event_id: str, request: UpdateEventRequest):
    """Update an existing calendar event."""
    try:
        # Set event_id from path parameter
        request.event_id = event_id
        
        event = update_event(request)
        return CalendarResponse(
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


@router.delete("/events/{event_id}", response_model=CalendarResponse)
async def delete_event_endpoint(event_id: str, send_notifications: bool = True):
    """Delete a calendar event."""
    try:
        success = delete_event(event_id, send_notifications)
        if success:
            return CalendarResponse(
                success=True,
                message="Event deleted successfully",
                data={'event_id': event_id}
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to delete event")
    except Exception as e:
        logger.error(f"Failed to delete event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete event: {str(e)}")


@router.get("/events/upcoming", response_model=List[CalendarEvent])
async def get_upcoming_events_endpoint(max_results: int = 10, days_ahead: int = 7):
    """Get upcoming events from the calendar."""
    try:
        events = get_upcoming_events(max_results, days_ahead)
        return events
    except Exception as e:
        logger.error(f"Failed to get upcoming events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get upcoming events: {str(e)}")


@router.get("/events/today", response_model=List[CalendarEvent])
async def get_today_events_endpoint():
    """Get events for today."""
    try:
        events = get_today_events()
        return events
    except Exception as e:
        logger.error(f"Failed to get today's events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get today's events: {str(e)}")


@router.get("/events/{event_id}", response_model=CalendarEvent)
async def get_event_endpoint(event_id: str):
    """Get a specific event by ID."""
    try:
        event = get_event(event_id)
        return event
    except Exception as e:
        logger.error(f"Failed to get event {event_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Event not found: {str(e)}")


# Search endpoints
@router.post("/events/search", response_model=EventsListResponse)
async def search_events_endpoint(request: SearchEventsRequest):
    """Search events using various criteria."""
    try:
        results = search_events(request)
        return results
    except Exception as e:
        logger.error(f"Failed to search events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search events: {str(e)}")


@router.get("/events/date-range", response_model=List[CalendarEvent])
async def get_events_by_date_range_endpoint(
    start_date: str, 
    end_date: str, 
    max_results: int = 100
):
    """Get events within a specific date range."""
    try:
        events = get_events_by_date_range(start_date, end_date, max_results)
        return events
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


# Monitoring endpoints
@router.post("/monitor/start", response_model=CalendarResponse)
async def start_calendar_monitoring_endpoint():
    """Start calendar monitoring in the background."""
    try:
        await start_calendar_monitoring()
        return CalendarResponse(
            success=True,
            message="Calendar monitoring started successfully",
            data={'status': 'monitoring_started'}
        )
    except Exception as e:
        logger.error(f"Failed to start calendar monitoring: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start calendar monitoring: {str(e)}")


@router.post("/monitor/stop", response_model=CalendarResponse)
async def stop_calendar_monitoring_endpoint():
    """Stop calendar monitoring."""
    try:
        stop_calendar_monitoring()
        return CalendarResponse(
            success=True,
            message="Calendar monitoring stopped successfully",
            data={'status': 'monitoring_stopped'}
        )
    except Exception as e:
        logger.error(f"Failed to stop calendar monitoring: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop calendar monitoring: {str(e)}")


@router.get("/monitor/status", response_model=Dict[str, Any])
async def get_monitor_status_endpoint():
    """Get the current status of calendar monitoring."""
    try:
        status = get_monitor_status()
        return {
            'success': True,
            'message': 'Monitor status retrieved successfully',
            'data': status
        }
    except Exception as e:
        logger.error(f"Failed to get monitor status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get monitor status: {str(e)}")


# Webhook endpoint for push notifications  
@router.post("/webhook/notifications")
async def handle_calendar_notification_endpoint(request: Request):
    """Handle incoming calendar push notifications."""
    try:
        # Extract headers
        headers = dict(request.headers)
        
        # Get request body (usually empty for calendar notifications)
        body = await request.body()
        body_str = body.decode('utf-8') if body else ""
        
        # Process the notification
        result = await handle_calendar_notification(headers, body_str)
        
        # Return success response to Google
        return Response(status_code=200, content="OK")
        
    except Exception as e:
        logger.error(f"Failed to handle calendar notification: {e}")
        # Return success to avoid Google retrying
        return Response(status_code=200, content="OK")
