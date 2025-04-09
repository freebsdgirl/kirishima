"""
This module defines data models for handling structured incoming messages and proxy requests.
Classes:
    IncomingMessage:
    ProxyRequest:
        Encapsulates the details of a proxy request, including the associated incoming message, 
        user ID, context, and optional parameters like mode and memories.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class IncomingMessage(BaseModel):
    """
    Represents a structured incoming message with platform-specific details.
    
    Captures essential information about a message, including its origin platform, 
    sender, content, timestamp, and optional metadata. Useful for standardizing 
    message representation across different communication platforms.
    
    Attributes:
        platform: The communication platform (e.g., 'imessage', 'sms').
        sender_id: Unique identifier for the message sender.
        text: The actual message content.
        timestamp: Precise time the message was sent in ISO 8601 format.
        metadata: Additional platform-specific information.
    """
    platform: str = Field(..., description="The platform from which the message originates (e.g., 'imessage').")
    sender_id: str = Field(..., description="The sender's identifier, such as a phone number or unique ID.")
    text: str = Field(..., description="The raw text content of the incoming message.")
    timestamp: str = Field(..., description="ISO 8601 formatted timestamp of when the message was sent.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional platform-specific metadata, e.g., chat IDs.")

    class Config:
        json_schema_extra = {
            "example": {
                "platform": "imessage",
                "sender_id": "+15555555555",
                "text": "Don’t forget your meds",
                "timestamp": "2025-04-09T04:00:00Z",
                "metadata": {
                    "chat_id": "BBUUID-ABC123"
                }
            }
        }


class ProxyRequest(BaseModel):
    """
    Represents a proxy request with message, user identification, context, and optional mode and memories.
    
    Attributes:
        message (IncomingMessage): The incoming message associated with the proxy request.
        user_id (str): The unique identifier of the user making the request.
        context (str): The context of the proxy request.
        mode (Optional[str], optional): An optional mode specification for the request. Defaults to None.
        memories (Optional[List[str]], optional): An optional list of memory references. Defaults to None.
    """
    message: IncomingMessage
    user_id: str
    context: str
    mode: Optional[str] = None
    memories: Optional[List[str]] = None
