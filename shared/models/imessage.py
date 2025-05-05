"""
This module defines the iMessage model using Pydantic's BaseModel.
Classes:
    iMessage: Represents an iMessage with core attributes such as id, author_id, timestamp, and content.
    ProxyiMessageRequest: Represents a request for sending an iMessage with associated metadata.
    OutgoingiMessage: Represents an outgoing iMessage with recipient address and message content.
"""


from shared.models.contacts import Contact
from shared.models.proxy import ChatMessage

from pydantic import BaseModel, Field
from typing import Optional, List


class iMessage(BaseModel):
    """
    Represents an iMessage with its core attributes.
    
    Attributes:
        id (str): Unique identifier for the message.
        author_id (str): Sender of the message.
        timestamp (str): Timestamp of when the message was sent.
        content (str): Content of the message.
    """
    id: str                             = Field(..., description="Unique identifier for the message")
    author_id: str                      = Field(..., description="Sender of the message")
    timestamp: str                      = Field(..., description="Timestamp of when the message was sent")
    content: str                        = Field(..., description="Content of the message")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "12345",
                    "author_id": "John Doe",
                    "timestamp": "2023-10-01T12:00:00Z",
                    "content": "Hello, how are you?"
                },
                {
                    "id": "67890",
                    "author_id": "Jane Smith",
                    "timestamp": "2023-10-01T12:05:00Z",
                    "content": "I'm good, thanks! How about you?"
                }
            ]
        }
    }


class ProxyiMessageRequest(BaseModel):
    """
    Represents a request for sending an iMessage with associated metadata.
    
    Attributes:
        message (iMessage): The iMessage object to be sent.
        mode (str): The mode in which the message is sent.
        memories (Optional[list]): List of memories associated with the message.
        summaries (Optional[str]): List of summaries associated with the message.
        platform (Optional[str]): The platform from which the message is sent, defaults to "imessage".
        is_admin (Optional[bool]): Indicates if the sender is an admin, defaults to False.
        contact (Contact): The contact associated with the message.
        messages (List[ChatMessage]): List of chat messages associated with the iMessage.
    """
    message: iMessage                   = Field(..., description="The iMessage object to be sent")
    mode: str                           = Field(..., description="The mode in which the message is sent")
    memories: Optional[list]            = Field(..., description="List of memories associated with the message")
    summaries: Optional[str]            = Field(..., description="List of summaries associated with the message")
    platform: Optional[str]             = Field("imessage", description="The platform from which the message is sent")
    is_admin: Optional[bool]            = Field(False, description="Indicates if the sender is an admin")
    contact: Contact                    = Field(..., description="The contact associated with the message")
    messages: List[ChatMessage]         = Field(..., description="List of chat messages associated with the iMessage")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": {
                        "id": "12345",
                        "author_id": "John Doe",
                        "timestamp": "2023-10-01 12:00:00Z",
                        "content": "Hello, how are you?"
                    },
                    "mode": "work",
                    "memories": ["memory1", "memory2"],
                    "summaries": ["summary1", "summary2"],
                    "platform": "imessage",
                    "is_admin": False,
                    "contact": {
                        # Contact details here
                    },
                    "messages": [
                        {
                            # Chat message details here
                        }
                    ]
                }
            ]
        }
    }


class OutgoingiMessage(BaseModel):
    """
    Represents an outgoing iMessage with recipient address and message content.
    
    Attributes:
        address (str): The phone number or contact address to send the message to.
        message (str): The text content of the message to be sent.
    """
    address: str                        = Field(..., description="The phone number or contact address to send the message to")
    message: str                        = Field(..., description="The text content of the message to be sent")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "address": "+1234567890",
                    "message": "Hello, this is a test message!"
                }
            ]
        }
    }
