"""
Calendar-specific models for GoogleAPI service.
Contains request and response models for Google Calendar operations.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CalendarEvent(BaseModel):
    """
    Represents a Google Calendar event.
    """
    id: Optional[str] = Field(None, description="Event ID")
    summary: Optional[str] = Field(None, description="Event title/summary")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")
    start: Optional[Dict[str, Any]] = Field(None, description="Event start time")
    end: Optional[Dict[str, Any]] = Field(None, description="Event end time")
    attendees: Optional[List[Dict[str, Any]]] = Field(None, description="Event attendees")
    creator: Optional[Dict[str, Any]] = Field(None, description="Event creator")
    organizer: Optional[Dict[str, Any]] = Field(None, description="Event organizer")
    status: Optional[str] = Field(None, description="Event status (confirmed, tentative, cancelled)")
    html_link: Optional[str] = Field(None, description="Link to event in Google Calendar")
    created: Optional[str] = Field(None, description="Event creation time")
    updated: Optional[str] = Field(None, description="Event last update time")
    recurring_event_id: Optional[str] = Field(None, description="ID of recurring event (if applicable)")
    transparency: Optional[str] = Field(None, description="Event transparency (opaque, transparent)")
    visibility: Optional[str] = Field(None, description="Event visibility (default, public, private, confidential)")
    reminders: Optional[Dict[str, Any]] = Field(None, description="Event reminders configuration")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "abc123def456",
                    "summary": "Team Meeting",
                    "description": "Weekly team sync meeting",
                    "location": "Conference Room A",
                    "start": {"dateTime": "2025-07-24T10:00:00-07:00", "timeZone": "America/Los_Angeles"},
                    "end": {"dateTime": "2025-07-24T11:00:00-07:00", "timeZone": "America/Los_Angeles"},
                    "status": "confirmed"
                }
            ]
        }
    }


class CreateEventRequest(BaseModel):
    """
    Request model for creating a calendar event.
    """
    summary: str = Field(..., description="Event title/summary")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")
    start_datetime: str = Field(..., description="Event start time (ISO 8601 format)")
    end_datetime: str = Field(..., description="Event end time (ISO 8601 format)")
    start_date: Optional[str] = Field(None, description="All-day event start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="All-day event end date (YYYY-MM-DD)")
    attendees: Optional[List[str]] = Field(None, description="List of attendee email addresses")
    send_notifications: Optional[bool] = Field(True, description="Whether to send notifications to attendees")
    transparency: Optional[str] = Field("opaque", description="Event transparency (opaque, transparent)")
    visibility: Optional[str] = Field("default", description="Event visibility (default, public, private, confidential)")
    reminders: Optional[Dict[str, Any]] = Field(
        {
            "useDefault": False,
            "overrides": [
                {
                    "method": "popup",
                    "minutes": 30
                }
            ]
        },
        description="Event reminders configuration"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Team Meeting",
                    "description": "Weekly team sync meeting",
                    "location": "Conference Room A",
                    "start_datetime": "2025-07-24T10:00:00-07:00",
                    "end_datetime": "2025-07-24T11:00:00-07:00",
                    "attendees": ["team@example.com", "manager@example.com"]
                }
            ]
        }
    }


class UpdateEventRequest(BaseModel):
    """
    Request model for updating a calendar event.
    """
    event_id: str = Field(..., description="Event ID to update")
    summary: Optional[str] = Field(None, description="Event title/summary")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")
    start_datetime: Optional[str] = Field(None, description="Event start time (ISO 8601 format)")
    end_datetime: Optional[str] = Field(None, description="Event end time (ISO 8601 format)")
    start_date: Optional[str] = Field(None, description="All-day event start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="All-day event end date (YYYY-MM-DD)")
    attendees: Optional[List[str]] = Field(None, description="List of attendee email addresses")
    send_notifications: Optional[bool] = Field(True, description="Whether to send notifications to attendees")
    transparency: Optional[str] = Field(None, description="Event transparency (opaque, transparent)")
    visibility: Optional[str] = Field(None, description="Event visibility (default, public, private, confidential)")
    reminders: Optional[Dict[str, Any]] = Field(None, description="Event reminders configuration")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "event_id": "abc123def456",
                    "summary": "Updated Team Meeting",
                    "location": "Conference Room B",
                    "start_datetime": "2025-07-24T11:00:00-07:00",
                    "end_datetime": "2025-07-24T12:00:00-07:00"
                }
            ]
        }
    }


class DeleteEventRequest(BaseModel):
    """
    Request model for deleting a calendar event.
    """
    event_id: str = Field(..., description="Event ID to delete")
    send_notifications: Optional[bool] = Field(True, description="Whether to send notifications to attendees")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "event_id": "abc123def456",
                    "send_notifications": True
                }
            ]
        }
    }


class SearchEventsRequest(BaseModel):
    """
    Request model for searching calendar events.
    """
    q: Optional[str] = Field(None, description="Free text search terms")
    time_min: Optional[str] = Field(None, description="Lower bound for event start time (ISO 8601)")
    time_max: Optional[str] = Field(None, description="Upper bound for event start time (ISO 8601)")
    max_results: Optional[int] = Field(10, description="Maximum number of events to return")
    order_by: Optional[str] = Field("startTime", description="Sort order (startTime, updated)")
    single_events: Optional[bool] = Field(True, description="Expand recurring events into individual instances")
    show_deleted: Optional[bool] = Field(False, description="Include deleted events")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "q": "meeting",
                    "time_min": "2025-07-24T00:00:00Z",
                    "time_max": "2025-07-31T23:59:59Z",
                    "max_results": 20
                }
            ]
        }
    }


class ListEventsRequest(BaseModel):
    """
    Request model for listing events in a date range.
    """
    start_date: str = Field(..., description="Start date in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)")
    end_date: str = Field(..., description="End date in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)")
    max_results: Optional[int] = Field(100, description="Maximum number of events to return")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "start_date": "2025-07-24T00:00:00Z",
                    "end_date": "2025-07-31T23:59:59Z",
                    "max_results": 50
                }
            ]
        }
    }


class EventsListResponse(BaseModel):
    """
    Response model for listing events.
    """
    events: List[CalendarEvent] = Field(..., description="List of events")
    next_page_token: Optional[str] = Field(None, description="Token for next page of results")
    updated: Optional[str] = Field(None, description="Last update time")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "events": [
                        {
                            "id": "abc123def456",
                            "summary": "Team Meeting",
                            "start": {"dateTime": "2025-07-24T10:00:00-07:00"},
                            "end": {"dateTime": "2025-07-24T11:00:00-07:00"}
                        }
                    ],
                    "updated": "2025-07-24T09:00:00Z"
                }
            ]
        }
    }


class CalendarListResponse(BaseModel):
    """
    Response model for listing calendars.
    """
    calendars: List[Dict[str, Any]] = Field(..., description="List of calendars")
    next_page_token: Optional[str] = Field(None, description="Token for next page of results")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "calendars": [
                        {
                            "id": "primary",
                            "summary": "Primary Calendar",
                            "accessRole": "owner"
                        }
                    ]
                }
            ]
        }
    } 