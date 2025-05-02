"""
This module defines the `DiscordDirectMessage` Pydantic model, which represents a direct message sent via Discord.

Classes:
    DiscordDirectMessage: 
        A Pydantic model representing a Discord direct message, including message ID, content, author information, display name, and timestamp.
"""

from pydantic import BaseModel
from datetime import datetime
from pydantic import Field
from typing import Optional


class DiscordDirectMessage(BaseModel):
    """
    A Pydantic model representing a Discord message.

    Attributes:
        message_id (str): The unique identifier for the message.
        content (str): The content of the message.
        author_id (str): The unique identifier for the author of the message.
        display_name (str): The display name of the author.
        timestamp (Optional[str]): The timestamp when the message was created.
    """
    message_id: int                     = Field(..., description="The unique identifier for the message.")
    content: str                        = Field(..., description="The content of the message.")
    author_id: int                      = Field(..., description="The unique identifier for the author of the message.")
    display_name: str                   = Field(..., description="The display name of the author.")
    timestamp: Optional[str]            = Field(default_factory=lambda: datetime.now().isoformat(), description="The timestamp when the message was created.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "message_id": 1234567890,
                "content": "Hello, how are you?",
                "author_id": 9876543210,
                "display_name": "John Doe",
                "timestamp": "2023-10-01T12:00:00Z"
            }
        }
    }
