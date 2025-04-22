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
        timestamp (str): The timestamp when the message was created.
    """
    message_id: int                     = Field(..., description="The unique identifier for the message.")
    content: str                        = Field(..., description="The content of the message.")
    author_id: int                      = Field(..., description="The unique identifier for the author of the message.")
    display_name: str                   = Field(..., description="The display name of the author.")
    timestamp: Optional[str]            = Field(default_factory=lambda: datetime.now().isoformat(), description="The timestamp when the message was created.")
    class Config:
        json_schema_extra = {
            "example": {
                "message_id": 123456789,
                "content": "Hello, world!",
                "author_id": 987654321,
                "display_name": "John Doe",
                "timestamp": "2023-10-01T12:34:56Z"
            }
        }