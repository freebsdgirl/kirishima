"""
GoogleAPI models package.
Re-exports all models from service-specific modules for backward compatibility.
"""

# Common models
from .common import ApiResponse

# Gmail models
from .gmail import (
    ForwardEmailRequest,
    SaveDraftRequest,
    SendEmailRequest,
    ReplyEmailRequest,
    SearchEmailRequest,
    EmailSearchByRequest,
    GetEmailByIdRequest,
)

# Calendar models
from .calendar import (
    CalendarEvent,
    CreateEventRequest,
    UpdateEventRequest,
    DeleteEventRequest,
    SearchEventsRequest,
    ListEventsRequest,
    EventsListResponse,
    CalendarListResponse,
)

# Tasks models
from .tasks import (
    TaskListModel,
    TaskModel,
    CreateTaskListRequest,
    CreateTaskRequest,
    UpdateTaskRequest,
    DueTasksResponse,
)

# Contacts models
from .contacts import (
    ContactName,
    ContactEmail,
    ContactPhoneNumber,
    ContactAddress,
    GoogleContact,
    ContactsListResponse,
    RefreshCacheResponse,
    CreateContactRequest,
    CreateContactResponse,
    SearchContactsRequest,
    UpdateContactRequest,
    DeleteContactRequest,
    ContactResponse,
)

# Re-export all models for backward compatibility
__all__ = [
    # Common
    "ApiResponse",
    
    # Gmail
    "ForwardEmailRequest",
    "SaveDraftRequest", 
    "SendEmailRequest",
    "ReplyEmailRequest",
    "SearchEmailRequest",
    "EmailSearchByRequest",
    "GetEmailByIdRequest",
    
    # Calendar
    "CalendarEvent",
    "CreateEventRequest",
    "UpdateEventRequest",
    "DeleteEventRequest",
    "SearchEventsRequest",
    "ListEventsRequest",
    "EventsListResponse",
    "CalendarListResponse",
    
    # Tasks
    "TaskListModel",
    "TaskModel",
    "CreateTaskListRequest",
    "CreateTaskRequest",
    "UpdateTaskRequest",
    "DueTasksResponse",
    
    # Contacts
    "ContactName",
    "ContactEmail",
    "ContactPhoneNumber",
    "ContactAddress",
    "GoogleContact",
    "ContactsListResponse",
    "RefreshCacheResponse",
    "CreateContactRequest",
    "CreateContactResponse",
    "SearchContactsRequest",
    "UpdateContactRequest",
    "DeleteContactRequest",
    "ContactResponse",
] 