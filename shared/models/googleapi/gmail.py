"""
Gmail-specific models for GoogleAPI service.
Contains request and response models for Gmail operations.
"""

from typing import Optional, List, Dict, Any
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
                    "thread_id": "18b8c0c0c0c0c0c0",
                    "body": "Please review this email thread",
                    "to": "colleague@example.com"
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
                    "subject": "Meeting Tomorrow",
                    "body": "Hi, let's meet tomorrow at 2 PM.",
                    "cc": "manager@example.com"
                }
            ]
        }
    }


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
                    "subject": "Project Update",
                    "body": "Here's the latest update on our project.",
                    "cc": "team@example.com",
                    "attachments": ["/path/to/document.pdf"]
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
                    "thread_id": "18b8c0c0c0c0c0c0",
                    "body": "Thanks for the information. I'll review it and get back to you."
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
                    "query": "from:john@example.com",
                    "max_results": 20
                },
                {
                    "query": "subject:meeting",
                    "max_results": 5
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
                    "value": "john@example.com",
                    "max_results": 15
                },
                {
                    "value": "meeting",
                    "max_results": 8
                }
            ]
        }
    }


class GetEmailByIdRequest(BaseModel):
    """
    Request model for retrieving an email by its ID.
    
    Attributes:
        email_id (str): The ID of the email to retrieve.
        format (Optional[str]): The format of the response (full, metadata, minimal, raw).
    """
    email_id: str = Field(..., description="Email ID to retrieve")
    format: Optional[str] = Field("full", description="Response format (full, metadata, minimal, raw)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email_id": "18b8c0c0c0c0c0c0",
                    "format": "full"
                }
            ]
        }
    } 