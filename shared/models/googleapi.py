
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ForwardEmailRequest(BaseModel):
    """
    Request model for forwarding an email.
    Attributes:
        thread_id (str): Thread ID of the email to forward.
        body (str): Preface body for the forwarded email.
        to (str): Recipient email address to forward to.
    """
    thread_id: str = Field(..., description="Thread ID of the email to forward")
    body: str = Field(..., description="Preface body for the forwarded email")
    to: str = Field(..., description="Recipient email address to forward to")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "thread_id": "1234567890abcdef",
                    "body": "Please see the forwarded message below:",
                    "to": "recipient@example.com"
                }
            ]
        }
    }


class SaveDraftRequest(BaseModel):
    """
    Request model for saving an email as a draft.
    
    Attributes:
        to (str): Recipient email address.
        subject (str): Email subject.
        body (str): Email body.
        from_email (Optional[str], optional): Sender email address. Defaults to None (uses authenticated user).
        cc (Optional[str], optional): CC recipient email address. Defaults to None.
        bcc (Optional[str], optional): BCC recipient email address. Defaults to None.
    """
    to: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body")
    from_email: Optional[str] = Field(None, description="Sender email address (optional, uses authenticated user)")
    cc: Optional[str] = Field(None, description="CC recipient email address")
    bcc: Optional[str] = Field(None, description="BCC recipient email address")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "to": "recipient@example.com",
                    "subject": "Draft Email",
                    "body": "This is a draft email to be reviewed before sending.",
                    "from_email": "sender@example.com",
                    "cc": "cc@example.com",
                    "bcc": "bcc@example.com"
                }
            ]
        }
    }
"""
Request/Response Models for Google API Email Operations.
This module defines Pydantic models for handling requests and responses related to email operations,
including sending, replying, and searching emails. Each model provides field-level descriptions and
example payloads for validation and documentation purposes.

Classes:
    SendEmailRequest: Model for sending an email, supporting recipients, subject, body, CC, BCC, and attachments.
    ReplyEmailRequest: Model for replying to an email thread, supporting reply body and attachments.
    SearchEmailRequest: Model for searching emails using a query string, with optional result limit.
    EmailSearchByRequest: Model for searching emails by a specific value, with optional result limit.
    EmailResponse: Model representing the result of an email operation, including success status, message, and optional data.

All models use Pydantic's Field for validation and documentation, and provide example payloads for schema generation.
"""


class SendEmailRequest(BaseModel):
    """
    Request model for sending an email.
    
    Attributes:
        to (str): Recipient email address.
        subject (str): Email subject.
        body (str): Email body.
        from_email (Optional[str], optional): Sender email address. Defaults to None (uses authenticated user).
        cc (Optional[str], optional): CC recipient email address. Defaults to None.
        bcc (Optional[str], optional): BCC recipient email address. Defaults to None.
        attachments (Optional[List[str]], optional): List of file paths for attachments. Defaults to None.
    """
    to: str                               = Field(..., description="Recipient email address")
    subject: str                          = Field(..., description="Email subject")
    body: str                             = Field(..., description="Email body")
    from_email: Optional[str]             = Field(None, description="Sender email address (optional, uses authenticated user)")
    cc: Optional[str]                     = Field(None, description="CC recipient email address")
    bcc: Optional[str]                    = Field(None, description="BCC recipient email address")
    attachments: Optional[List[str]]      = Field(None, description="List of file paths for attachments")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "to": "recipient@example.com",
                    "subject": "Hello",
                    "body": "This is a test email.",
                    "from_email": "sender@example.com",
                    "cc": "cc@example.com",
                    "bcc": "bcc@example.com",
                    "attachments": ["path/to/attachment1.txt", "path/to/attachment2.jpg"]
                }
            ]
        }
    }


class ReplyEmailRequest(BaseModel):
    """
    Request model for replying to an email.
        
    Attributes:
        thread_id (str): Thread ID of the email to reply to.
        body (str): Reply email body.
        attachments (Optional[List[str]], optional): List of file paths for attachments. Defaults to None.
    """
    thread_id: str                        = Field(..., description="Thread ID of the email to reply to")
    body: str                             = Field(..., description="Reply email body")
    attachments: Optional[List[str]]      = Field(None, description="List of file paths for attachments")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "thread_id": "1234567890abcdef",
                    "body": "Thank you for your email!",
                    "attachments": ["path/to/attachment1.txt", "path/to/attachment2.jpg"]
                }
            ]
        }
    }


class SearchEmailRequest(BaseModel):
    """
    Request model for searching emails with a specific query.
        
    Attributes:
        query (str): The search query to find emails.
        max_results (Optional[int]): Maximum number of email search results to return, 
                                     defaulting to 10 if not specified.
    """
    query: str                            = Field(..., description="Search query")
    max_results: Optional[int]            = Field(10, description="Maximum number of results to return")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "from:example@example.com"
                }
            ]
        }
    }


class EmailSearchByRequest(BaseModel):
    """
    Request model for searching emails by a specific value.
    
    Attributes:
        value (str): The search value to query emails.
        max_results (Optional[int]): Maximum number of email search results to return, 
                                     defaulting to 10 if not specified.
    """
    value: str                            = Field(..., description="Search value")
    max_results: Optional[int]            = Field(10, description="Maximum number of results to return")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "value": "<search_value>",
                    "max_results": 10
                }
            ]
        }
    }

class EmailResponse(BaseModel):
    """
    Response model for email operations representing the result of an email-related action.
    
    Attributes:
        success (bool): Indicates whether the email operation was completed successfully.
        message (str): A descriptive message about the result of the email operation.
        data (Optional[Dict[str, Any]]): Optional dictionary containing additional response details, such as message ID.
    """
    success: bool                         = Field(..., description="Indicates if the operation was successful")
    message: str                          = Field(..., description="Response message")
    data: Optional[Dict[str, Any]]        = Field(None, description="Response data")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Email sent successfully",
                    "data": {
                        "message_id": "1234567890abcdef"
                    }
                },
                {
                    "success": False,
                    "message": "Failed to send email",
                    "data": None
                }
            ]
        }
    }


# Google Contacts Models
class ContactName(BaseModel):
    """
    Represents a contact's name information.
    """
    display_name: Optional[str] = Field(None, description="The contact's display name")
    given_name: Optional[str] = Field(None, description="The contact's first name")
    family_name: Optional[str] = Field(None, description="The contact's last name")
    middle_name: Optional[str] = Field(None, description="The contact's middle name")


class ContactEmail(BaseModel):
    """
    Represents a contact's email address.
    """
    value: str = Field(..., description="The email address")
    type: Optional[str] = Field(None, description="The type of email (home, work, etc.)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Email metadata")


class ContactPhoneNumber(BaseModel):
    """
    Represents a contact's phone number.
    """
    value: str = Field(..., description="The phone number")
    type: Optional[str] = Field(None, description="The type of phone number (home, work, mobile, etc.)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Phone number metadata")


class ContactAddress(BaseModel):
    """
    Represents a contact's address.
    """
    formatted_value: Optional[str] = Field(None, description="The formatted address")
    street_address: Optional[str] = Field(None, description="Street address")
    city: Optional[str] = Field(None, description="City")
    region: Optional[str] = Field(None, description="State/region")
    postal_code: Optional[str] = Field(None, description="Postal/ZIP code")
    country: Optional[str] = Field(None, description="Country")
    type: Optional[str] = Field(None, description="The type of address (home, work, etc.)")


class GoogleContact(BaseModel):
    """
    Represents a Google contact with all available information.
    """
    resource_name: str = Field(..., description="The contact's resource name (ID)")
    etag: Optional[str] = Field(None, description="The contact's etag for versioning")
    names: Optional[List[ContactName]] = Field(None, description="The contact's names")
    email_addresses: Optional[List[ContactEmail]] = Field(None, description="The contact's email addresses")
    phone_numbers: Optional[List[ContactPhoneNumber]] = Field(None, description="The contact's phone numbers")
    addresses: Optional[List[ContactAddress]] = Field(None, description="The contact's addresses")
    organizations: Optional[List[Dict[str, Any]]] = Field(None, description="The contact's organizations")
    birthdays: Optional[List[Dict[str, Any]]] = Field(None, description="The contact's birthdays")
    photos: Optional[List[Dict[str, Any]]] = Field(None, description="The contact's photos")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Contact metadata")
    created_time: Optional[str] = Field(None, description="When the contact was created")
    modified_time: Optional[str] = Field(None, description="When the contact was last modified")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "resource_name": "people/c12345",
                    "etag": "abc123",
                    "names": [
                        {
                            "display_name": "John Doe",
                            "given_name": "John",
                            "family_name": "Doe"
                        }
                    ],
                    "email_addresses": [
                        {
                            "value": "john@example.com",
                            "type": "work"
                        }
                    ],
                    "phone_numbers": [
                        {
                            "value": "+1234567890",
                            "type": "mobile"
                        }
                    ]
                }
            ]
        }
    }


class ContactsListResponse(BaseModel):
    """
    Response model for listing contacts.
    """
    contacts: List[GoogleContact] = Field(..., description="List of contacts")
    next_page_token: Optional[str] = Field(None, description="Token for next page of results")
    total_items: Optional[int] = Field(None, description="Total number of contacts")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "contacts": [],
                    "next_page_token": "abc123",
                    "total_items": 150
                }
            ]
        }
    }


class RefreshCacheResponse(BaseModel):
    """
    Response model for cache refresh operations.
    """
    success: bool = Field(..., description="Whether the cache refresh was successful")
    message: str = Field(..., description="Status message")
    contacts_refreshed: int = Field(..., description="Number of contacts refreshed")
    timestamp: str = Field(..., description="Timestamp of the refresh operation")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Cache refreshed successfully",
                    "contacts_refreshed": 150,
                    "timestamp": "2023-01-01T12:00:00Z"
                }
            ]
        }
    }


class CreateContactRequest(BaseModel):
    """
    Request model for creating a new contact.
    """
    display_name: Optional[str] = Field(None, description="The contact's display name")
    given_name: Optional[str] = Field(None, description="The contact's first name")
    family_name: Optional[str] = Field(None, description="The contact's last name")
    middle_name: Optional[str] = Field(None, description="The contact's middle name")
    email_addresses: Optional[List[ContactEmail]] = Field(None, description="The contact's email addresses")
    phone_numbers: Optional[List[ContactPhoneNumber]] = Field(None, description="The contact's phone numbers")
    addresses: Optional[List[ContactAddress]] = Field(None, description="The contact's addresses")
    organizations: Optional[List[Dict[str, Any]]] = Field(None, description="The contact's organizations")
    notes: Optional[str] = Field(None, description="Notes about the contact")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "display_name": "John Doe",
                    "given_name": "John",
                    "family_name": "Doe",
                    "email_addresses": [
                        {
                            "value": "john@example.com",
                            "type": "work"
                        }
                    ],
                    "phone_numbers": [
                        {
                            "value": "+1234567890",
                            "type": "mobile"
                        }
                    ],
                    "notes": "Important contact"
                }
            ]
        }
    }


class CreateContactResponse(BaseModel):
    """
    Response model for contact creation operations.
    """
    success: bool = Field(..., description="Whether the contact creation was successful")
    message: str = Field(..., description="Status message")
    contact: Optional[GoogleContact] = Field(None, description="The created contact data")
    resource_name: Optional[str] = Field(None, description="The resource name of the created contact")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Contact created successfully",
                    "contact": {
                        "resource_name": "people/c12345",
                        "names": [{"display_name": "John Doe"}]
                    },
                    "resource_name": "people/c12345"
                }
            ]
        }
    }


# Google Calendar Models
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

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Team Meeting",
                    "description": "Weekly team sync meeting",
                    "location": "Conference Room A",
                    "start_datetime": "2025-07-24T10:00:00-07:00",
                    "end_datetime": "2025-07-24T11:00:00-07:00",
                    "attendees": ["john@example.com", "jane@example.com"],
                    "send_notifications": True
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

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "event_id": "abc123def456",
                    "summary": "Updated Team Meeting",
                    "description": "Updated weekly team sync meeting",
                    "location": "Conference Room B",
                    "start_datetime": "2025-07-24T14:00:00-07:00",
                    "end_datetime": "2025-07-24T15:00:00-07:00"
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
                            "primary": True,
                            "accessRole": "owner"
                        }
                    ],
                    "next_page_token": None
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
                    "events": [],
                    "next_page_token": None,
                    "updated": "2025-07-24T12:00:00Z"
                }
            ]
        }
    }


class CalendarResponse(BaseModel):
    """
    Response model for calendar operations.
    """
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Event created successfully",
                    "data": {
                        "event_id": "abc123def456",
                        "html_link": "https://calendar.google.com/event?eid=..."
                    }
                }
            ]
        }
    }


# Google Tasks Models

class TaskListModel(BaseModel):
    """
    Model representing a Google Tasks task list.
    """
    id: str = Field(..., description="The task list ID")
    title: str = Field(..., description="The task list title/name")
    updated: Optional[str] = Field(None, description="Last update timestamp")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "MTIzNDU2Nzg5MDEyMzQ1Njc4OTA",
                    "title": "Shopping List",
                    "updated": "2025-07-24T10:30:00.000Z"
                }
            ]
        }
    }


class TaskModel(BaseModel):
    """
    Model representing a Google Tasks task with Kirishima metadata support.
    """
    id: str = Field(..., description="The task ID")
    title: str = Field(..., description="The task title/content")
    notes: Optional[str] = Field(None, description="Task notes/details (may contain Kirishima metadata)")
    status: str = Field(..., description="Task status (needsAction, completed)")
    due: Optional[str] = Field(None, description="Due date in RFC 3339 format (date only)")
    completed: Optional[str] = Field(None, description="Completion timestamp")
    updated: Optional[str] = Field(None, description="Last update timestamp")
    
    # Parsed Kirishima metadata (extracted from notes)
    kirishima_due_time: Optional[str] = Field(None, description="Due time in HH:MM format (parsed from notes)")
    kirishima_rrule: Optional[str] = Field(None, description="RFC 5545 RRULE for recurrence (parsed from notes)")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "MTIzNDU2Nzg5MDEyMzQ1Njc4OTA",
                    "title": "Call dentist",
                    "status": "needsAction",
                    "due": "2025-07-25",
                    "kirishima_due_time": "14:30",
                    "kirishima_rrule": "FREQ=MONTHLY;INTERVAL=1"
                }
            ]
        }
    }


class CreateTaskListRequest(BaseModel):
    """
    Request model for creating a new task list.
    """
    title: str = Field(..., description="The title/name for the new task list")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Shopping List"
                }
            ]
        }
    }


class CreateTaskRequest(BaseModel):
    """
    Request model for creating a new task.
    """
    title: str = Field(..., description="The task title/content")
    notes: Optional[str] = Field(None, description="Additional task notes (separate from Kirishima metadata)")
    due: Optional[str] = Field(None, description="Due date in YYYY-MM-DD format")
    due_time: Optional[str] = Field(None, description="Due time in HH:MM format (24-hour)")
    rrule: Optional[str] = Field(None, description="RFC 5545 RRULE for recurrence (e.g., 'FREQ=DAILY;INTERVAL=1')")
    task_list_id: Optional[str] = Field(None, description="Task list ID (defaults to stickynotes list)")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Call dentist",
                    "notes": "Schedule annual cleaning",
                    "due": "2025-07-25",
                    "due_time": "14:30",
                    "rrule": "FREQ=MONTHLY;INTERVAL=1"
                }
            ]
        }
    }


class UpdateTaskRequest(BaseModel):
    """
    Request model for updating an existing task.
    """
    title: Optional[str] = Field(None, description="The task title/content")
    notes: Optional[str] = Field(None, description="Additional task notes")
    due: Optional[str] = Field(None, description="Due date in YYYY-MM-DD format")
    due_time: Optional[str] = Field(None, description="Due time in HH:MM format (24-hour)")
    rrule: Optional[str] = Field(None, description="RFC 5545 RRULE for recurrence")
    status: Optional[str] = Field(None, description="Task status (needsAction, completed)")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Call dentist - rescheduled",
                    "due": "2025-07-26",
                    "due_time": "15:00"
                }
            ]
        }
    }


class TasksResponse(BaseModel):
    """
    Response model for Google Tasks operations.
    """
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Task created successfully",
                    "data": {
                        "task_id": "MTIzNDU2Nzg5MDEyMzQ1Njc4OTA",
                        "title": "Call dentist"
                    }
                }
            ]
        }
    }


class DueTasksResponse(BaseModel):
    """
    Response model for checking due tasks - designed for brain service consumption.
    """
    success: bool = Field(..., description="Whether the operation was successful")
    due_tasks: List[TaskModel] = Field(..., description="List of tasks that are due now")
    overdue_tasks: List[TaskModel] = Field(..., description="List of tasks that are overdue")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "due_tasks": [
                        {
                            "id": "MTIzNDU2Nzg5MDEyMzQ1Njc4OTA",
                            "title": "Call dentist",
                            "status": "needsAction",
                            "due": "2025-07-24",
                            "kirishima_due_time": "14:30"
                        }
                    ],
                    "overdue_tasks": []
                }
            ]
        }
    }


class NaturalLanguageRequest(BaseModel):
    """
    Request model for natural language Google API interactions.
    """
    query: str = Field(..., description="Natural language query for Google services")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "send joanne newman an email with the text: Randi says she'll eat dinner with you tonight."
            }
        }
    }


class GoogleServiceAction(BaseModel):
    """
    Model representing an action to take with a Google service.
    """
    service: str = Field(..., description="The Google service to use (gmail, calendar, contacts)")
    action: str = Field(..., description="The action to perform")
    parameters: Dict[str, Any] = Field(..., description="Parameters for the action")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "service": "gmail",
                "action": "send_email",
                "parameters": {
                    "to": "joanne newman",
                    "subject": "Dinner Tonight",
                    "body": "Randi says she'll eat dinner with you tonight."
                }
            }
        }
    }


class NaturalLanguageResponse(BaseModel):
    """
    Response model for natural language Google API interactions.
    """
    success: bool = Field(..., description="Whether the operation was successful")
    action_taken: Optional[GoogleServiceAction] = Field(None, description="The action that was performed")
    result: Optional[Dict[str, Any]] = Field(None, description="The result of the action")
    error: Optional[str] = Field(None, description="Error message if operation failed")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "action_taken": {
                    "service": "gmail",
                    "action": "send_email",
                    "parameters": {
                        "to": "joanne.newman@example.com",
                        "subject": "Dinner Tonight",
                        "body": "Randi says she'll eat dinner with you tonight."
                    }
                },
                "result": {
                    "email_id": "abc123",
                    "message": "Email sent successfully"
                }
            }
        }
    }