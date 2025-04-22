"""
This module defines Pydantic models for representing user and conversation messages exchanged between users and the system across various platforms.

Classes:
    RawUserMessage: Represents a raw user message exchanged between a user and the system, including sender information, platform, role, and content.
    CanonicalUserMessage: Represents a canonical user message with unique ID, timestamps, and message metadata for storage and retrieval.
    RawConversationMessage: Represents a raw message within a conversation, typically for storing or processing messages from different platforms.
    CanonicalConversationMessage: Represents a canonical message within a conversation, including unique ID, timestamps, and message metadata for persistent storage.
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class RawUserMessage(BaseModel):
    """
    Represents a raw user message exchanged between a user and the system.

    Attributes:
        user_id (str): Sender's unique ID.
        platform (str): Origin platform (e.g., 'api', 'discord', etc).
        platform_msg_id (Optional[str]): Optional platform-specific message ID.
        role (str): Role of the message sender, either 'user' or 'assistant'.
        content (str): Message body.
    """
    user_id: str                                = Field(..., description="Sender's unique ID")
    platform: str                               = Field(..., description="Origin platform ('api','discord',etc)")
    platform_msg_id: Optional[str]              = Field(None, description="Optional platform‑specific message ID")
    role: str                                   = Field(..., description="'user' or 'assistant'")
    content: str                                = Field(..., description="Message body")


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
    """
    id: int                                     = Field(..., description="Unique message ID")
    user_id: str                                = Field(..., description="Sender's unique ID")
    platform: str                               = Field(..., description="Origin platform ('api','discord',etc)")
    platform_msg_id: Optional[str]              = Field(None, description="Optional platform‑specific message ID")
    role: str                                   = Field(..., description="'user' or 'assistant'")
    content: str                                = Field(..., description="Message body")
    created_at: str                             = Field(..., description="Message creation timestamp")
    updated_at: str                             = Field(..., description="Message update timestamp")


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


class DeleteSummary(BaseModel):
    """
    Represents a summary of a delete operation, tracking the number of rows deleted.
    
    Attributes:
        deleted (int): The total number of rows that were successfully deleted during the operation.
    """
    deleted: int                                = Field(..., description="Number of rows deleted")


class UserSummary(BaseModel):
    id: int                                     = Field(..., description="Unique message ID")
    user_id: str                                = Field(..., description="Sender's unique ID")
    content: str                                = Field(..., description="Summarized message content")
    level: int                                  = Field(..., description="Level of the summarized messages")
    timestamp_begin: str                        = Field(..., description="Start timestamp of the summarized messages")
    timestamp_end: str                          = Field(..., description="End timestamp of the summarized messages")
    timestamp_summarized: str                   = Field(..., description="Timestamp when the message was summarized")

class UserSummaryList(BaseModel):
    summaries: List[UserSummary]                = Field(..., description="List of summarized messages")

class DeleteRequest(BaseModel):
    ids: List[int]                              = Field(..., min_items=1, description="IDs to delete")

class ConversationSummary(BaseModel):
    id: int                                     = Field(..., description="Unique message ID")
    conversation_id: str                        = Field(..., description="Discord channel / thread ID")
    content: str                                = Field(..., description="Summarized message content")
    period: str                                 = Field(..., description="daily, weekly, or monthly")
    timestamp_begin: str                        = Field(..., description="Start timestamp of the summarized messages")
    timestamp_end: str                          = Field(..., description="End timestamp of the summarized messages")
    timestamp_summarized: str                   = Field(..., description="Timestamp when the message was summarized")

class ConversationSummaryList(BaseModel):
    summaries: List[ConversationSummary]        = Field(..., description="List of summarized messages")
