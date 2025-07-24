
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