"""
Calendar event management utilities.

This module provides functions for creating, updating, and deleting calendar events
using the Google Calendar API.

Functions:
    create_event(): Create a new calendar event
    update_event(): Update an existing calendar event
    delete_event(): Delete a calendar event
    get_event(): Get a specific event by ID
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from shared.models.googleapi import CreateEventRequest, UpdateEventRequest, CalendarEvent
from app.services.calendar.auth import get_calendar_service, get_calendar_id
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta


def create_event(request: CreateEventRequest) -> Dict[str, Any]:
    """
    Create a new calendar event.
    
    Args:
        request: CreateEventRequest with event details
        
    Returns:
        Dict containing the created event data
        
    Raises:
        Exception: If event creation fails
    """
    try:
        service = get_calendar_service()
        calendar_id = get_calendar_id()
        
        # Build event object
        event = {
            'summary': request.summary,
            'transparency': request.transparency,
            'visibility': request.visibility
        }
        
        if request.description:
            event['description'] = request.description
            
        if request.location:
            event['location'] = request.location
        
        # Handle datetime vs all-day events
        if request.start_datetime and request.end_datetime:
            # Timed event
            event['start'] = {'dateTime': request.start_datetime}
            event['end'] = {'dateTime': request.end_datetime}
        elif request.start_date and request.end_date:
            # All-day event
            event['start'] = {'date': request.start_date}
            event['end'] = {'date': request.end_date}
        else:
            raise ValueError("Must specify either datetime or date for start/end times")
        
        # Add attendees if specified
        if request.attendees:
            event['attendees'] = [{'email': email} for email in request.attendees]
        
        # Add reminders if specified
        if request.reminders:
            event['reminders'] = request.reminders
        
        # Create the event
        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event,
            sendNotifications=request.send_notifications
        ).execute()
        
        logger.info(f"Created event: {created_event.get('id')} - {created_event.get('summary')}")
        
        return created_event
        
    except Exception as e:
        logger.error(f"Failed to create event: {e}")
        raise


def update_event(request: UpdateEventRequest) -> Dict[str, Any]:
    """
    Update an existing calendar event.
    
    Args:
        request: UpdateEventRequest with updated event details
        
    Returns:
        Dict containing the updated event data
        
    Raises:
        Exception: If event update fails
    """
    try:
        service = get_calendar_service()
        calendar_id = get_calendar_id()
        
        # Get existing event
        existing_event = service.events().get(
            calendarId=calendar_id,
            eventId=request.event_id
        ).execute()
        
        # Update only provided fields
        if request.summary is not None:
            existing_event['summary'] = request.summary
            
        if request.description is not None:
            existing_event['description'] = request.description
            
        if request.location is not None:
            existing_event['location'] = request.location
            
        if request.transparency is not None:
            existing_event['transparency'] = request.transparency
            
        if request.visibility is not None:
            existing_event['visibility'] = request.visibility
        
        # Handle datetime updates
        if request.start_datetime and request.end_datetime:
            existing_event['start'] = {'dateTime': request.start_datetime}
            existing_event['end'] = {'dateTime': request.end_datetime}
        elif request.start_date and request.end_date:
            existing_event['start'] = {'date': request.start_date}
            existing_event['end'] = {'date': request.end_date}
        
        # Update attendees if specified
        if request.attendees is not None:
            existing_event['attendees'] = [{'email': email} for email in request.attendees]
        
        # Update reminders if specified
        if request.reminders is not None:
            existing_event['reminders'] = request.reminders
        
        # Update the event
        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=request.event_id,
            body=existing_event,
            sendNotifications=request.send_notifications
        ).execute()
        
        logger.info(f"Updated event: {updated_event.get('id')} - {updated_event.get('summary')}")
        
        return updated_event
        
    except Exception as e:
        logger.error(f"Failed to update event {request.event_id}: {e}")
        raise


def delete_event(event_id: str, send_notifications: bool = True) -> bool:
    """
    Delete a calendar event.
    
    Args:
        event_id: ID of the event to delete
        send_notifications: Whether to send notifications to attendees
        
    Returns:
        bool: True if deletion was successful
        
    Raises:
        Exception: If event deletion fails
    """
    try:
        service = get_calendar_service()
        calendar_id = get_calendar_id()
        
        service.events().delete(
            calendarId=calendar_id,
            eventId=event_id,
            sendNotifications=send_notifications
        ).execute()
        
        logger.info(f"Deleted event: {event_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete event {event_id}: {e}")
        raise


def get_event(event_id: str) -> CalendarEvent:
    """
    Get a specific event by ID.
    
    Args:
        event_id: ID of the event to retrieve
        
    Returns:
        CalendarEvent: The requested event
        
    Raises:
        Exception: If event retrieval fails
    """
    try:
        service = get_calendar_service()
        calendar_id = get_calendar_id()
        
        event = service.events().get(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()
        
        logger.info(f"Retrieved event: {event.get('id')} - {event.get('summary')}")
        
        # Convert to CalendarEvent model
        return CalendarEvent(**event)
        
    except Exception as e:
        logger.error(f"Failed to get event {event_id}: {e}")
        raise


def get_upcoming_events(max_results: int = 10, days_ahead: int = 7) -> List[CalendarEvent]:
    """
    Get upcoming events from the calendar.
    
    Args:
        max_results: Maximum number of events to return
        days_ahead: Number of days ahead to look for events
        
    Returns:
        List[CalendarEvent]: List of upcoming events
    """
    try:
        service = get_calendar_service()
        calendar_id = get_calendar_id()
        
        # Calculate time range
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
        
        logger.info(f"Retrieved {len(events)} upcoming events")
        
        # Convert to CalendarEvent models
        return [CalendarEvent(**event) for event in events]
        
    except Exception as e:
        logger.error(f"Failed to get upcoming events: {e}")
        raise
