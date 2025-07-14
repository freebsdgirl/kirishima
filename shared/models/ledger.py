"""
This module defines a set of Pydantic models for representing and processing user messages and conversation messages 
in both raw and canonical forms, as well as a summary model for delete operations.
Classes:
    RawUserMessage:
        Represents a raw user message exchanged between a user and the system. Includes attributes such as user ID, 
        platform, role, and message content.
    CanonicalUserMessage:
        Represents a canonical user message exchanged between a user and an assistant. Includes additional attributes 
        such as unique message ID, creation timestamp, and update timestamp.
    RawConversationMessage:
        Represents a raw message within a conversation, typically used for storing or processing messages from various 
        platforms. Includes attributes such as conversation ID, platform, role, and message content.
    CanonicalConversationMessage:
        Represents a canonical message within a conversation, typically used for storing and retrieving messages from 
        various platforms. Includes additional attributes such as unique message ID, creation timestamp, and update 
        timestamp.
    DeleteSummary:
        Represents a summary of a delete operation, tracking the number of rows deleted during the operation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime
from uuid import uuid4


class RawUserMessage(BaseModel):
    """
    Represents a raw user message exchanged between a user and the system.

    Attributes:
        user_id (str): Sender's unique ID.
        platform (str): Origin platform (e.g., 'api', 'discord', etc).
        platform_msg_id (Optional[str]): Optional platform-specific message ID.
        role (str): Role of the message sender, either 'user' or 'assistant'.
        content (str): Message body.
        model (Optional[str]): Model/mode used for this message (e.g., 'default', 'nsfw').
        tool_calls (Optional[dict]): Tool call requests as dict/JSON.
        function_call (Optional[dict]): Function call content as dict/JSON.
    """
    user_id: str                                = Field(..., description="Sender's unique ID")
    platform: str                               = Field(..., description="Origin platform ('api','discord',etc)")
    platform_msg_id: Optional[str]              = Field(None, description="Optional platform‑specific message ID")
    role: str                                   = Field(..., description="'user' or 'assistant'")
    content: str                                = Field(..., description="Message body")
    model: Optional[str]                        = Field(None, description="Model/mode used for this message (e.g., 'default', 'nsfw')")
    tool_calls: Optional[dict]                  = Field(None, description="Tool call requests as dict/JSON")
    function_call: Optional[dict]               = Field(None, description="Function call content as dict/JSON")
    tool_call_id: Optional[str]                 = Field(None, description="Tool call ID for tool messages")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "1234567890",
                "platform": "discord",
                "platform_msg_id": "9876543210",
                "role": "user",
                "content": "Hello, how are you?",
                "model": "default",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": "{\"location\": \"New York\"}"
                        }
                    }
                ],
                "function_call": {
                    "name": "get_weather",
                    "arguments": "{\"location\": \"New York\"}"
                }
            }
        }
    }


class CanonicalUserMessage(BaseModel):
    """
    Represents a canonical user message exchanged between a user and an assistant.

    Attributes:
        id (int): Unique message ID.
        user_id (str): Sender's unique identifier.
        platform (str): Origin platform (e.g., 'api', 'discord').
        platform_msg_id (Optional[str]): Optional platform-specific message ID.
        role (str): Role of the message sender ('user' or 'assistant').
        content (str): Message body content.
        created_at (str): Timestamp when the message was created.
        updated_at (str): Timestamp when the message was last updated.
        model (Optional[str]): Model/mode used for this message (e.g., 'default', 'nsfw').
        tool_calls (Optional[dict]): Tool call requests as dict/JSON.
        function_call (Optional[dict]): Function call content as dict/JSON.
    """
    id: int                                     = Field(..., description="Unique message ID")
    user_id: str                                = Field(..., description="Sender's unique ID")
    platform: str                               = Field(..., description="Origin platform ('api','discord',etc)")
    platform_msg_id: Optional[str]              = Field(None, description="Optional platform‑specific message ID")
    role: str                                   = Field(..., description="'user' or 'assistant'")
    content: str                                = Field(..., description="Message body")
    model: Optional[str]                        = Field(None, description="Model/mode used for this message (e.g., 'default', 'nsfw')")
    tool_calls: Optional[dict]                  = Field(None, description="Tool call requests as dict/JSON")
    function_call: Optional[dict]               = Field(None, description="Function call content as dict/JSON")
    tool_call_id: Optional[str]                 = Field(None, description="Tool call ID for tool messages")
    created_at: str                             = Field(..., description="Message creation timestamp")
    updated_at: str                             = Field(..., description="Message update timestamp")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 1,
                "user_id": "1234567890",
                "platform": "discord",
                "platform_msg_id": "9876543210",
                "role": "user",
                "content": "Hello, how are you?",
                "model": "default",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": "{\"location\": \"New York\"}"
                        }
                    }
                ],
                "function_call": {
                    "name": "get_weather",
                    "arguments": "{\"location\": \"New York\"}"
                },
                "created_at": "2023-10-01 12:00:00Z",
                "updated_at": "2023-10-01 12:00:00Z"
            }
        }
    }


class RawConversationMessage(BaseModel):
    """
    Represents a raw message within a conversation, typically used for storing or processing messages from various platforms.

    Attributes:
        conversation_id (str): Discord channel or thread ID associated with the message.
        platform (str): Origin platform of the message (e.g., 'api', 'discord').
        role (str): Role of the message sender, either 'user' or 'assistant'.
        content (str): The body of the message.
    """
    conversation_id: str                        = Field(..., description="Discord channel / thread ID")
    platform: str                               = Field(..., description="Origin platform ('api','discord',etc)")
    role: str                                   = Field(..., description="'user' or 'assistant'")
    content: str                                = Field(..., description="Message body")

    model_config = {
        "json_schema_extra": {
            "example": {
                "conversation_id": "1234567890",
                "platform": "discord",
                "role": "user",
                "content": "Hello, how are you?"
            }
        }
    }


class CanonicalConversationMessage(BaseModel):
    """
    Represents a canonical message within a conversation, typically used for storing and retrieving messages
    from various platforms (e.g., Discord, API).

    Attributes:
        id (int): Unique message ID.
        conversation_id (str): Discord channel or thread ID associated with the message.
        platform (str): Origin platform of the message (e.g., 'api', 'discord').
        role (str): Role of the message sender, either 'user' or 'assistant'.
        content (str): The body of the message.
        created_at (str): Timestamp indicating when the message was created.
        updated_at (str): Timestamp indicating when the message was last updated.
    """
    id: int                                     = Field(..., description="Unique message ID")
    conversation_id: str                        = Field(..., description="Discord channel / thread ID")
    platform: str                               = Field(..., description="Origin platform ('api','discord',etc)")
    role: str                                   = Field(..., description="'user' or 'assistant'")
    content: str                                = Field(..., description="Message body")
    created_at: str                             = Field(..., description="Message creation timestamp")
    updated_at: str                             = Field(..., description="Message update timestamp")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 1,
                "conversation_id": "1234567890",
                "platform": "discord",
                "role": "user",
                "content": "Hello, how are you?",
                "created_at": "2023-10-01T12:00:00Z",
                "updated_at": "2023-10-01T12:00:00Z"
            }
        }
    }


class DeleteSummary(BaseModel):
    """
    Represents a summary of a delete operation, tracking the number of rows deleted.
    
    Attributes:
        deleted (int): The total number of rows that were successfully deleted during the operation.
    """
    deleted: int                                = Field(..., description="Number of rows deleted")

    model_config = {
        "json_schema_extra": {
            "example": {
                "deleted": 5
            }
        }
    }

# --- Summary Models (moved from shared/models/summary.py) ---
class SummaryType(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    PERIODIC = "periodic"

class SummaryMetadata(BaseModel):
    timestamp_begin: str                = Field(..., description="Start timestamp of the summary")
    timestamp_end: str                  = Field(..., description="End timestamp of the summary")
    summary_type: SummaryType           = Field(..., description="Type of the summary (e.g., daily, weekly)")
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timestamp_begin": "2023-10-01T00:00:00Z",
                    "timestamp_end": "2023-10-31T23:59:59Z",
                    "summary_type": SummaryType.MONTHLY
                },
                {
                    "timestamp_begin": "2023-10-01 08:00:00Z",
                    "timestamp_end": "2023-10-01 12:00:00Z",
                    "summary_type": SummaryType.MORNING
                }
            ]
        }
    }

class Summary(BaseModel):
    id: str                             = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for the summary")
    content: str                        = Field(..., description="Content of the summary")
    metadata: Optional[SummaryMetadata] = Field(None, description="Metadata associated with the summary")
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "content": "This is a summary of the events that occurred in October 2023.",
                    "metadata": {
                        "timestamp_begin": "2023-10-01 00:00:00Z",
                        "timestamp_end": "2023-10-31 23:59:59Z",
                        "summary_type": SummaryType.MONTHLY
                    }
                },
                {
                    "id": "123e4567-e89b-12d3-a456-426614174001",
                    "content": "This is a summary of the morning events on October 1, 2023.",
                    "metadata": {
                        "timestamp_begin": "2023-10-01 08:00:00Z",
                        "timestamp_end": "2023-10-01 12:00:00Z",
                        "summary_type": SummaryType.MORNING
                    }
                }
            ]
        }
    }

class SummaryCreateRequest(BaseModel):
    period: List[str]               = Field(..., description="Time period for the summary (e.g., 'daily', 'weekly', 'monthly')")
    date: str                       = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"), description="Starting date in YYYY-MM-DD format.")
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "period": ["daily"],
                    "date": "2023-10-01"
                },
                {
                    "period": ["weekly"],
                    "date": "2023-10-01"
                }
            ]
        }
    }

class CombinedSummaryRequest(BaseModel):
    summaries: List[Summary] = Field(..., description="List of summaries to be combined")
    max_tokens: int = Field(..., description="Maximum number of tokens for the combined summary")
    user_alias: Optional[str] = Field(None, description="User alias for the summary")
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summaries": [
                        {
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                            "content": "This is a summary of the events that occurred in October 2023.",
                            "metadata": {
                                "timestamp_begin": "2023-10-01 00:00:00Z",
                                "timestamp_end": "2023-10-31 23:59:59Z",
                                "summary_type": SummaryType.MONTHLY
                            }
                        },
                        {
                            "id": "123e4567-e89b-12d3-a456-426614174001",
                            "content": "This is a summary of the morning events on October 1, 2023.",
                            "metadata": {
                                "timestamp_begin": "2023-10-01 08:00:00Z",
                                "timestamp_end": "2023-10-01 12:00:00Z",
                                "summary_type": SummaryType.MORNING
                            }
                        }
                    ],
                    "max_tokens": 100,
                    "user_alias": "User123"
                }
            ]
        }
    }

class SummaryRequest(BaseModel):
    messages: List[CanonicalUserMessage]        = Field(..., description="List of user messages to summarize")
    user_alias: Optional[str]                   = Field(None, description="Alias for the user in the conversation")
    max_tokens: int                             = Field(..., description="Maximum number of tokens for the summary")
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "messages": [
                        {
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                            "content": "This is a user message.",
                            "created_at": "2023-10-01 00:00:00Z",
                            "user_id": "123e4567-e89b-12d3-a456-426614174000"
                        },
                        {
                            "id": "123e4567-e89b-12d3-a456-426614174001",
                            "content": "This is another user message.",
                            "created_at": "2023-10-01 01:00:00Z",
                            "user_id": "123e4567-e89b-12d3-a456-426614174001"
                        }
                    ],
                    "user_alias": "User123",
                    "max_tokens": 100
                }
            ]
        }
    }
