"""
GoogleAPI models - re-export from modular structure.
This file maintains backward compatibility by importing all models from the new modular structure.
"""

# Import all models from the new modular structure
from .googleapi import *

# Re-export everything for backward compatibility
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





