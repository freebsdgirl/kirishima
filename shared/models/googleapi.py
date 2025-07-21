
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