"""
This module defines data models for summarization requests and message buffer operations.
Classes:
    SummarizeRequest:
    MessageBufferEntry:
        Config:
            json_schema_extra (dict): Example schema for the model.
    AddMessageBufferResponse:
        Config:
            json_schema_extra (dict): Example schema for the model.
"""

from datetime import datetime
from pydantic import BaseModel, Field


class SummarizeRequest(BaseModel):
    """
    Represents a request for summarizing text with optional database storage.
    
    Attributes:
        save (bool): Flag to determine whether the summary should be saved in a database. Defaults to True.
        timestamp (str): Timestamp of the summary request, automatically set to the current UTC time.
        text (str): The text content to be summarized.
        platform (str): Comma-separated list of platforms associated with the summary.
        user_id (str): Unique identifier of the user from the contacts microservice.
    """
    save: bool = Field(default=True)    # Whether to save the summary in a database
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())  # Timestamp of the request
    text: str                           # text to summarize
    platform: str                       # comma separated list of platforms
    user_id: str                        # uuid from contacts microservice


class MessageBufferEntry(BaseModel):
    """
    Represents an entry in the message buffer with detailed message metadata.
    
    Captures comprehensive information about a message, including its content, source,
    associated user, communication platform, and precise timestamp. Used for tracking
    and managing message interactions within the system.
    
    Attributes:
        text (str): The actual content of the message.
        source (str): Origin of the message, either 'User' or 'Kirishima'.
        user_id (str): Unique identifier for the user related to the message.
        platform (str): Communication platform where the message was sent.
        timestamp (str): Message timestamp in ISO 8601 format.
    """
    text: str = Field(..., description="The content of the message.")
    source: str = Field(..., description="Indicates the origin of the message, either 'User' or 'Kirishima'.")
    user_id: str = Field(..., description="Unique identifier for the user associated with the message.")
    platform: str = Field(..., description="The communication platform where the message was sent.")
    timestamp: str = Field(..., description="The message's timestamp in ISO 8601 string format.")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Don’t forget your meds",
                "source": "User",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "platform": "imessage",
                "timestamp": "2025-04-09T04:10:00Z"
            }
        }


class AddMessageBufferResponse(BaseModel):
    """
    Represents the response from adding an entry to the message buffer.
    
    Captures the result of an operation to add a message to the buffer, 
    including the operation's status and the unique identifier of the newly created buffer entry.
    
    Attributes:
        status (str): Indicates the outcome of the buffer entry addition operation (e.g., 'success' or 'failure').
        id (str): The unique identifier assigned to the newly added buffer entry.
    """
    status: str = Field(..., description="The status of the buffer entry addition operation.")
    id: str = Field(..., description="The unique identifier of the newly added buffer entry.")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "id": "buffer_entry_001"
            }
        }